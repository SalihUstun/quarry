using System.ComponentModel.DataAnnotations;

namespace Quarry.Gateway.Features.Auth;

internal sealed class AuthOptions
{
    public const string SectionName = "Auth";

    [Required]
    [EmailAddress]
    public string DevUserEmail { get; init; } = string.Empty;

    [Required]
    [MinLength(8)]
    public string DevUserPassword { get; init; } = string.Empty;

    public Guid TenantId { get; init; } = Guid.Parse("00000000-0000-0000-0000-000000000001");
}

internal sealed class JwtOptions
{
    public const string SectionName = "Jwt";

    [Required]
    public string Issuer { get; init; } = "quarry-gateway";

    [Required]
    public string Audience { get; init; } = "quarry";

    [Required]
    [MinLength(32)]
    public string SigningKey { get; init; } = string.Empty;

    [Range(5, 1440)]
    public int LifetimeMinutes { get; init; } = 480;
}
