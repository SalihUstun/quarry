using System.Security.Claims;
using System.Text;
using Microsoft.Extensions.Options;
using Microsoft.IdentityModel.JsonWebTokens;
using Microsoft.IdentityModel.Tokens;

namespace Quarry.Gateway.Features.Auth;

internal sealed record IssuedToken(string Value, DateTimeOffset ExpiresAt);

internal sealed class TokenService(IOptions<JwtOptions> options, TimeProvider timeProvider)
{
    private readonly JwtOptions _options = options.Value;
    private readonly JsonWebTokenHandler _handler = new();

    public static SymmetricSecurityKey CreateSigningKey(string signingKey) =>
        new(Encoding.UTF8.GetBytes(signingKey));

    public IssuedToken Issue(CurrentUser user)
    {
        var now = timeProvider.GetUtcNow();
        var expiresAt = now.AddMinutes(_options.LifetimeMinutes);
        var token = _handler.CreateToken(new SecurityTokenDescriptor
        {
            Issuer = _options.Issuer,
            Audience = _options.Audience,
            Subject = new ClaimsIdentity(
            [
                new Claim(JwtRegisteredClaimNames.Sub, user.UserId),
                new Claim(CurrentUser.TenantIdClaim, user.TenantId.ToString()),
            ]),
            IssuedAt = now.UtcDateTime,
            NotBefore = now.UtcDateTime,
            Expires = expiresAt.UtcDateTime,
            SigningCredentials = new SigningCredentials(
                CreateSigningKey(_options.SigningKey), SecurityAlgorithms.HmacSha256),
        });

        return new IssuedToken(token, expiresAt);
    }
}
