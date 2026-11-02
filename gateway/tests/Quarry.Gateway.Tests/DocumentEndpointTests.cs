using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text;

namespace Quarry.Gateway.Tests;

[Collection(PostgresTestGroup.Name)]
public sealed class DocumentEndpointTests(PostgresFixture postgres) : IAsyncLifetime
{
    private sealed record DocumentResponse(Guid Id, string FileName, string Status, string? Error, long SizeBytes);

    private static readonly Uri DocumentsUri = new("/api/documents", UriKind.Relative);
    private static readonly byte[] MinimalPdf = Encoding.ASCII.GetBytes("%PDF-1.7\n1 0 obj << >> endobj\n%%EOF");

    public Task InitializeAsync() => postgres.ExecuteAsync("TRUNCATE chunks, documents");

    public Task DisposeAsync() => Task.CompletedTask;

    [Fact]
    public async Task Upload_Pdf_StoresFileCreatesPendingDocumentAndRequestsIngestion()
    {
        await using var factory = new GatewayFactory(connectionString: postgres.ConnectionString);
        using var client = await factory.CreateAuthenticatedClientAsync();

        using var response = await client.PostAsync(DocumentsUri, FileContent("İzin Politikası.pdf", MinimalPdf));

        Assert.Equal(HttpStatusCode.Accepted, response.StatusCode);
        var document = await response.Content.ReadFromJsonAsync<DocumentResponse>();
        Assert.NotNull(document);
        Assert.Equal("İzin Politikası.pdf", document.FileName);
        Assert.Equal("pending", document.Status);
        Assert.Equal(MinimalPdf.Length, document.SizeBytes);
        Assert.Equal([document.Id], factory.AiService.IngestionRequests);

        var storedPath = Path.Combine(factory.UploadsPath, GatewayFactory.TenantId.ToString(), $"{document.Id}.pdf");
        Assert.Equal(MinimalPdf, await File.ReadAllBytesAsync(storedPath));
        var status = await postgres.ScalarAsync<string>("SELECT status FROM documents WHERE id = $1", document.Id);
        Assert.Equal("pending", status);
    }

    [Theory]
    [InlineData("rapor.pdf", "bu bir pdf değil")]
    [InlineData("program.exe", "MZ")]
    [InlineData("notlar.txt", "\0\0binary")]
    public async Task Upload_UnsupportedOrSpoofedFile_ReturnsBadRequest(string fileName, string content)
    {
        await using var factory = new GatewayFactory(connectionString: postgres.ConnectionString);
        using var client = await factory.CreateAuthenticatedClientAsync();

        using var response = await client.PostAsync(DocumentsUri, FileContent(fileName, Encoding.UTF8.GetBytes(content)));

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.Empty(factory.AiService.IngestionRequests);
    }

    [Fact]
    public async Task Upload_WhenAiServiceUnavailable_MarksDocumentFailed()
    {
        await using var factory = new GatewayFactory(
            new FakeAiServiceClient(acceptsIngestion: false), postgres.ConnectionString);
        using var client = await factory.CreateAuthenticatedClientAsync();

        using var response = await client.PostAsync(DocumentsUri, FileContent("notlar.txt", "Şirket notları"u8.ToArray()));

        var document = await response.Content.ReadFromJsonAsync<DocumentResponse>();
        Assert.NotNull(document);
        Assert.Equal("failed", document.Status);
        Assert.NotNull(document.Error);
    }

    [Fact]
    public async Task Upload_WithoutSession_ReturnsUnauthorized()
    {
        await using var factory = new GatewayFactory(connectionString: postgres.ConnectionString);
        using var client = factory.CreateHttpsClient();

        using var response = await client.PostAsync(DocumentsUri, FileContent("a.pdf", MinimalPdf));

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task List_ReturnsOnlyDocumentsOfCurrentTenant()
    {
        var otherTenant = Guid.NewGuid();
        await postgres.ExecuteAsync("INSERT INTO tenants (id, name) VALUES ($1, 'Başka Şirket')", otherTenant);
        await postgres.ExecuteAsync(
            """
            INSERT INTO documents (tenant_id, file_name, content_type, storage_path, size_bytes, uploaded_by)
            VALUES ($1, 'gizli.pdf', 'application/pdf', 'x/gizli.pdf', 1, 'baskasi@sirket.com')
            """,
            otherTenant);
        await using var factory = new GatewayFactory(connectionString: postgres.ConnectionString);
        using var client = await factory.CreateAuthenticatedClientAsync();
        using var upload = await client.PostAsync(DocumentsUri, FileContent("acik.pdf", MinimalPdf));

        var documents = await client.GetFromJsonAsync<List<DocumentResponse>>(DocumentsUri);

        Assert.NotNull(documents);
        Assert.Equal(["acik.pdf"], documents.Select(document => document.FileName));
    }

    private static MultipartFormDataContent FileContent(string fileName, byte[] bytes)
    {
        var file = new ByteArrayContent(bytes);
        file.Headers.ContentType = new MediaTypeHeaderValue("application/octet-stream");
        return new MultipartFormDataContent { { file, "file", fileName } };
    }
}
