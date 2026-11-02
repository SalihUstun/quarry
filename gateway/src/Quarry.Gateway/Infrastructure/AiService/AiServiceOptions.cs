using System.ComponentModel.DataAnnotations;

namespace Quarry.Gateway.Infrastructure.AiService;

internal sealed class AiServiceOptions
{
    public const string SectionName = "AiService";

    [Required]
    [Url]
    public string BaseUrl { get; init; } = string.Empty;

    [Range(1, 300)]
    public int TimeoutSeconds { get; init; } = 3;
}
