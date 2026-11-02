using System.Text.Unicode;

namespace Quarry.Gateway.Features.Documents;

internal sealed record SupportedFormat(string Extension, string ContentType);

internal static class UploadValidator
{
    public static readonly SupportedFormat Pdf = new(".pdf", "application/pdf");
    public static readonly SupportedFormat PlainText = new(".txt", "text/plain");

    private static readonly byte[] PdfSignature = "%PDF-"u8.ToArray();
    private const int SniffLength = 8192;

    public static async Task<SupportedFormat?> DetectAsync(IFormFile file, CancellationToken cancellationToken)
    {
        var extension = Path.GetExtension(file.FileName).ToLowerInvariant();
        var header = await ReadHeaderAsync(file, cancellationToken);

        return extension switch
        {
            ".pdf" when header.AsSpan().StartsWith(PdfSignature) => Pdf,
            ".txt" when IsUtf8Text(header) => PlainText,
            _ => null,
        };
    }

    public static string SafeFileName(string fileName)
    {
        var name = Path.GetFileName(fileName.Replace('\\', '/')).Trim();
        var invalid = Path.GetInvalidFileNameChars();
        var cleaned = new string(name.Select(character => invalid.Contains(character) ? '_' : character).ToArray());
        return cleaned.Length <= 255 ? cleaned : cleaned[^255..];
    }

    private static async Task<byte[]> ReadHeaderAsync(IFormFile file, CancellationToken cancellationToken)
    {
        await using var stream = file.OpenReadStream();
        var buffer = new byte[Math.Min(SniffLength, file.Length)];
        await stream.ReadExactlyAsync(buffer, cancellationToken);
        return buffer;
    }

    private static bool IsUtf8Text(byte[] header)
    {
        if (header.Contains((byte)0))
        {
            return false;
        }

        var maxTruncatedBytes = Math.Min(3, header.Length);
        for (var trim = 0; trim <= maxTruncatedBytes; trim++)
        {
            if (Utf8.IsValid(header.AsSpan(0, header.Length - trim)))
            {
                return true;
            }
        }

        return false;
    }
}
