use std::fs::File;
use std::io::Read;
use std::path::Path;

use pdfium_render::prelude::Pdfium;
use quarry_text::PageText;
use quick_xml::events::{BytesStart, Event};
use quick_xml::{Reader, XmlVersion};

use crate::error::ProcessError;

pub const PDF: &str = "application/pdf";
pub const PLAIN_TEXT: &str = "text/plain";
pub const DOCX: &str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

pub fn extract_pages(
    pdfium: &Pdfium,
    path: &Path,
    content_type: &str,
) -> Result<Vec<PageText>, ProcessError> {
    let pages = match content_type {
        PDF => extract_pdf(pdfium, path)?,
        PLAIN_TEXT => vec![PageText {
            page_number: 1,
            text: String::from_utf8_lossy(&read_file(path)?).into_owned(),
        }],
        DOCX => extract_docx(File::open(path).map_err(extraction_error)?)?,
        other => return Err(ProcessError::UnsupportedContentType(other.to_owned())),
    };

    if pages.iter().all(|page| page.text.trim().is_empty()) {
        return Err(ProcessError::NoText);
    }
    Ok(pages)
}

fn extract_pdf(pdfium: &Pdfium, path: &Path) -> Result<Vec<PageText>, ProcessError> {
    let document = pdfium
        .load_pdf_from_file(path, None)
        .map_err(extraction_error)?;
    let mut pages = Vec::new();
    for (index, page) in document.pages().iter().enumerate() {
        let text = page.text().map_err(extraction_error)?.all();
        pages.push(PageText {
            page_number: page_number(index),
            text,
        });
    }
    Ok(pages)
}

fn page_number(index: usize) -> u32 {
    u32::try_from(index + 1).unwrap_or(u32::MAX)
}

fn read_file(path: &Path) -> Result<Vec<u8>, ProcessError> {
    std::fs::read(path).map_err(extraction_error)
}

fn extraction_error(error: impl std::fmt::Display) -> ProcessError {
    ProcessError::Extraction(error.to_string())
}

pub fn extract_docx(archive: impl Read + std::io::Seek) -> Result<Vec<PageText>, ProcessError> {
    let mut archive = zip::ZipArchive::new(archive).map_err(extraction_error)?;
    let mut xml = String::new();
    archive
        .by_name("word/document.xml")
        .map_err(extraction_error)?
        .read_to_string(&mut xml)
        .map_err(extraction_error)?;
    parse_document_xml(&xml)
}

fn parse_document_xml(xml: &str) -> Result<Vec<PageText>, ProcessError> {
    let mut reader = Reader::from_str(xml);
    let mut builder = PageBuilder::default();
    let mut inside_text = false;

    loop {
        match reader.read_event().map_err(extraction_error)? {
            Event::Start(element) if element.name().as_ref() == "w:t" => inside_text = true,
            Event::End(element) => match element.name().as_ref() {
                "w:t" => inside_text = false,
                "w:p" => builder.push('\n'),
                _ => {}
            },
            Event::Empty(element) => builder.apply_empty_element(&element),
            Event::Text(text) if inside_text => {
                builder.push_str(&text.xml_content(XmlVersion::Implicit1_0));
            }
            Event::GeneralRef(reference) if inside_text => {
                let resolved = reference.resolve_char_ref().map_err(extraction_error)?;
                match resolved {
                    Some(character) => builder.push(character),
                    None => builder.push_str(
                        quick_xml::escape::resolve_predefined_entity(&reference.into_inner())
                            .unwrap_or_default(),
                    ),
                }
            }
            Event::Eof => break,
            _ => {}
        }
    }
    Ok(builder.finish())
}

#[derive(Default)]
struct PageBuilder {
    pages: Vec<PageText>,
    current: String,
}

impl PageBuilder {
    fn push(&mut self, character: char) {
        self.current.push(character);
    }

    fn push_str(&mut self, text: &str) {
        self.current.push_str(text);
    }

    fn apply_empty_element(&mut self, element: &BytesStart<'_>) {
        match element.name().as_ref() {
            "w:tab" => self.push('\t'),
            "w:lastRenderedPageBreak" => self.break_page(),
            "w:br" if is_page_break(element) => self.break_page(),
            "w:br" => self.push('\n'),
            _ => {}
        }
    }

    fn break_page(&mut self) {
        if !self.current.trim().is_empty() {
            let text = std::mem::take(&mut self.current);
            self.pages.push(PageText {
                page_number: page_number(self.pages.len()),
                text,
            });
        }
    }

    fn finish(mut self) -> Vec<PageText> {
        self.break_page();
        self.pages
    }
}

fn is_page_break(element: &BytesStart<'_>) -> bool {
    element
        .attributes()
        .flatten()
        .any(|attribute| attribute.key.as_ref() == "w:type" && attribute.value.as_ref() == "page")
}

#[cfg(test)]
mod tests {
    use std::io::{Cursor, Write};

    use zip::write::SimpleFileOptions;

    use super::*;

    fn docx_with(document_xml: &str) -> Cursor<Vec<u8>> {
        let mut buffer = Cursor::new(Vec::new());
        {
            let mut writer = zip::ZipWriter::new(&mut buffer);
            writer
                .start_file("word/document.xml", SimpleFileOptions::default())
                .expect("start zip entry");
            writer
                .write_all(document_xml.as_bytes())
                .expect("write zip entry");
            writer.finish().expect("finish zip");
        }
        buffer.set_position(0);
        buffer
    }

    #[test]
    fn docx_paragraphs_become_lines_and_page_breaks_start_new_pages() {
        let xml = r#"<w:document><w:body>
            <w:p><w:r><w:t>Yıllık izin </w:t></w:r><w:r><w:t>14 gündür.</w:t></w:r></w:p>
            <w:p><w:r><w:t>Ar&amp;Ge &#351;irketi</w:t><w:tab/><w:t>X</w:t></w:r></w:p>
            <w:p><w:r><w:br w:type="page"/><w:t>İkinci sayfa</w:t></w:r></w:p>
        </w:body></w:document>"#;

        let pages = extract_docx(docx_with(xml)).expect("valid docx");

        assert_eq!(
            pages,
            [
                PageText {
                    page_number: 1,
                    text: "Yıllık izin 14 gündür.\nAr&Ge şirketi\tX\n".to_owned()
                },
                PageText {
                    page_number: 2,
                    text: "İkinci sayfa\n".to_owned()
                },
            ]
        );
    }

    fn pdfium_from_env() -> Option<Pdfium> {
        let directory = std::env::var("PDFIUM_LIBRARY_DIR").ok()?;
        let bindings =
            Pdfium::bind_to_library(Pdfium::pdfium_platform_library_name_at_path(&directory))
                .expect("PDFIUM_LIBRARY_DIR points to a loadable PDFium library");
        Some(Pdfium::new(bindings))
    }

    fn repository_file(relative: &str) -> std::path::PathBuf {
        Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../../..")
            .join(relative)
    }

    #[test]
    fn extracts_sample_pdf_pages_with_pdfium() {
        let Some(pdfium) = pdfium_from_env() else {
            eprintln!("PDFIUM_LIBRARY_DIR is not set, skipping PDFium test");
            return;
        };

        let pages = extract_pages(
            &pdfium,
            &repository_file("samples/calisan-el-kitabi.pdf"),
            PDF,
        )
        .expect("sample PDF is readable");

        assert_eq!(
            pages
                .iter()
                .map(|page| page.page_number)
                .collect::<Vec<_>>(),
            [1, 2, 3]
        );
        assert!(pages[0].text.contains("uzaktan çalışabilir"));
        assert!(pages[1].text.contains("14 iş günü"));
        assert!(pages[2].text.contains("750 TL"));
    }

    #[test]
    fn corrupt_pdf_is_an_extraction_error() {
        let Some(pdfium) = pdfium_from_env() else {
            return;
        };
        let path = std::env::temp_dir().join(format!("quarry-corrupt-{}.pdf", std::process::id()));
        std::fs::write(&path, b"%PDF-1.7 broken").expect("write temp file");

        let result = extract_pages(&pdfium, &path, PDF);

        std::fs::remove_file(&path).ok();
        assert!(matches!(result, Err(ProcessError::Extraction(_))));
    }

    #[test]
    fn non_docx_archive_is_an_extraction_error() {
        let result = extract_docx(Cursor::new(b"not a zip".to_vec()));

        assert!(matches!(result, Err(ProcessError::Extraction(_))));
    }

    #[test]
    fn text_outside_w_t_elements_is_ignored() {
        let pages = parse_document_xml(
            "<w:document><w:instrText>PAGE</w:instrText><w:p><w:t>Metin</w:t></w:p></w:document>",
        )
        .expect("valid xml");

        assert_eq!(pages[0].text, "Metin\n");
    }
}
