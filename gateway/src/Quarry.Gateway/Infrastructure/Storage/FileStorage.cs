using System.ComponentModel.DataAnnotations;
using Microsoft.Extensions.Options;

namespace Quarry.Gateway.Infrastructure.Storage;

internal sealed class StorageOptions
{
    public const string SectionName = "Storage";

    [Required]
    public string UploadsPath { get; init; } = string.Empty;

    [Range(1, 500L * 1024 * 1024)]
    public long MaxFileSizeBytes { get; init; } = 50L * 1024 * 1024;
}

internal interface IFileStorage
{
    Task SaveAsync(string relativePath, Stream content, CancellationToken cancellationToken);

    void Delete(string relativePath);
}

internal sealed class LocalFileStorage(IOptions<StorageOptions> options) : IFileStorage
{
    private readonly string _root = Path.GetFullPath(options.Value.UploadsPath);

    public async Task SaveAsync(string relativePath, Stream content, CancellationToken cancellationToken)
    {
        var path = Resolve(relativePath);
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        await using var file = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.None);
        await content.CopyToAsync(file, cancellationToken);
    }

    public void Delete(string relativePath) => File.Delete(Resolve(relativePath));

    private string Resolve(string relativePath)
    {
        var path = Path.GetFullPath(Path.Combine(_root, relativePath));
        if (!path.StartsWith(_root + Path.DirectorySeparatorChar, StringComparison.Ordinal))
        {
            throw new InvalidOperationException("Storage path escapes the uploads directory");
        }

        return path;
    }
}
