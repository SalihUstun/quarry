using Microsoft.EntityFrameworkCore;

namespace Quarry.Gateway.Infrastructure.Persistence;

internal static class DocumentStatus
{
    public const string Pending = "pending";
    public const string Failed = "failed";
}

internal sealed class DocumentEntity
{
    public Guid Id { get; init; }
    public Guid TenantId { get; init; }
    public required string FileName { get; init; }
    public required string ContentType { get; init; }
    public required string StoragePath { get; init; }
    public long SizeBytes { get; init; }
    public string Status { get; set; } = DocumentStatus.Pending;
    public string? Error { get; set; }
    public int? PageCount { get; init; }
    public required string UploadedBy { get; init; }
    public DateTimeOffset CreatedAt { get; init; }
    public DateTimeOffset UpdatedAt { get; set; }
}

internal sealed class QuarryDbContext(DbContextOptions<QuarryDbContext> options) : DbContext(options)
{
    public DbSet<DocumentEntity> Documents => Set<DocumentEntity>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<DocumentEntity>(document =>
        {
            document.ToTable("documents");
            document.HasKey(entity => entity.Id);
        });
    }
}
