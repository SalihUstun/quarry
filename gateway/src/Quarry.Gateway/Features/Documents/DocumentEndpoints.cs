using Microsoft.AspNetCore.Http.HttpResults;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Options;
using Quarry.Gateway.Features.Auth;
using Quarry.Gateway.Infrastructure.Messaging;
using Quarry.Gateway.Infrastructure.Persistence;
using Quarry.Gateway.Infrastructure.Storage;

namespace Quarry.Gateway.Features.Documents;

internal sealed record DocumentResponse(
    Guid Id,
    string FileName,
    string Status,
    string? Error,
    int? PageCount,
    long SizeBytes,
    DateTimeOffset CreatedAt)
{
    public static DocumentResponse From(DocumentEntity document) => new(
        document.Id,
        document.FileName,
        document.Status,
        document.Error,
        document.PageCount,
        document.SizeBytes,
        document.CreatedAt);
}

internal static class DocumentEndpoints
{
    public const string QueueUnavailableError = "İşleme kuyruğuna ulaşılamadı. Lütfen tekrar yükleyin.";

    public static IEndpointRouteBuilder MapDocumentEndpoints(this IEndpointRouteBuilder routes)
    {
        var group = routes.MapGroup("/api/documents").RequireAuthorization();
        group.MapGet("/", ListAsync);
        group.MapGet("/{id:guid}", GetAsync);
        group.MapPost("/", UploadAsync).DisableAntiforgery();
        return routes;
    }

    private static async Task<List<DocumentResponse>> ListAsync(
        HttpContext context, QuarryDbContext db, CancellationToken cancellationToken)
    {
        var user = CurrentUser.Required(context.User);
        var documents = await db.Documents.AsNoTracking()
            .Where(document => document.TenantId == user.TenantId)
            .OrderByDescending(document => document.CreatedAt)
            .Take(200)
            .ToListAsync(cancellationToken);
        return documents.ConvertAll(DocumentResponse.From);
    }

    private static async Task<Results<Ok<DocumentResponse>, NotFound>> GetAsync(
        Guid id, HttpContext context, QuarryDbContext db, CancellationToken cancellationToken)
    {
        var user = CurrentUser.Required(context.User);
        var document = await db.Documents.AsNoTracking()
            .SingleOrDefaultAsync(entity => entity.Id == id && entity.TenantId == user.TenantId, cancellationToken);
        return document is null ? TypedResults.NotFound() : TypedResults.Ok(DocumentResponse.From(document));
    }

    private static async Task<Results<Accepted<DocumentResponse>, ProblemHttpResult>> UploadAsync(
        IFormFile file,
        HttpContext context,
        QuarryDbContext db,
        IFileStorage storage,
        IIngestionQueue ingestionQueue,
        IOptions<StorageOptions> storageOptions,
        TimeProvider timeProvider,
        CancellationToken cancellationToken)
    {
        if (file.Length == 0 || file.Length > storageOptions.Value.MaxFileSizeBytes)
        {
            return BadRequest("Dosya boş veya izin verilen boyuttan büyük.");
        }

        var format = await UploadValidator.DetectAsync(file, cancellationToken);
        if (format is null)
        {
            return BadRequest("Sadece PDF, Word (.docx) ve UTF-8 metin (.txt) dosyaları desteklenir.");
        }

        var user = CurrentUser.Required(context.User);
        var documentId = Guid.NewGuid();
        var storagePath = $"{user.TenantId}/{documentId}{format.Extension}";
        await using (var content = file.OpenReadStream())
        {
            await storage.SaveAsync(storagePath, content, cancellationToken);
        }

        var now = timeProvider.GetUtcNow();
        var document = new DocumentEntity
        {
            Id = documentId,
            TenantId = user.TenantId,
            FileName = UploadValidator.SafeFileName(file.FileName),
            ContentType = format.ContentType,
            StoragePath = storagePath,
            SizeBytes = file.Length,
            UploadedBy = user.UserId,
            CreatedAt = now,
            UpdatedAt = now,
        };
        db.Documents.Add(document);
        try
        {
            await db.SaveChangesAsync(cancellationToken);
        }
        catch
        {
            storage.Delete(storagePath);
            throw;
        }

        if (!await ingestionQueue.EnqueueAsync(documentId, cancellationToken))
        {
            document.Status = DocumentStatus.Failed;
            document.Error = QueueUnavailableError;
            document.UpdatedAt = timeProvider.GetUtcNow();
            await db.SaveChangesAsync(cancellationToken);
        }

        return TypedResults.Accepted($"/api/documents/{documentId}", DocumentResponse.From(document));
    }

    private static ProblemHttpResult BadRequest(string title) =>
        TypedResults.Problem(title: title, statusCode: StatusCodes.Status400BadRequest);
}
