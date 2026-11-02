using System.Security.Claims;
using Microsoft.IdentityModel.JsonWebTokens;

namespace Quarry.Gateway.Features.Auth;

internal sealed record CurrentUser(string UserId, Guid TenantId)
{
    public const string TenantIdClaim = "tenant_id";

    public static CurrentUser? From(ClaimsPrincipal principal)
    {
        var userId = principal.FindFirstValue(JwtRegisteredClaimNames.Sub);
        var tenantClaim = principal.FindFirstValue(TenantIdClaim);
        return userId is not null && Guid.TryParse(tenantClaim, out var tenantId)
            ? new CurrentUser(userId, tenantId)
            : null;
    }

    public static CurrentUser Required(ClaimsPrincipal principal) =>
        From(principal) ?? throw new InvalidOperationException("Authenticated user has no identity claims");
}
