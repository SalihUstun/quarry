using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.Extensions.Options;
using Microsoft.IdentityModel.Tokens;

namespace Quarry.Gateway.Features.Auth;

internal static class AuthRegistration
{
    public static IServiceCollection AddQuarryAuth(this IServiceCollection services)
    {
        services.AddOptions<AuthOptions>()
            .BindConfiguration(AuthOptions.SectionName)
            .ValidateDataAnnotations()
            .ValidateOnStart();
        services.AddOptions<JwtOptions>()
            .BindConfiguration(JwtOptions.SectionName)
            .ValidateDataAnnotations()
            .ValidateOnStart();

        services.AddSingleton(TimeProvider.System);
        services.AddSingleton<TokenService>();

        services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme).AddJwtBearer();
        services.AddOptions<JwtBearerOptions>(JwtBearerDefaults.AuthenticationScheme)
            .Configure<IOptions<JwtOptions>>((bearer, jwtOptions) =>
            {
                var jwt = jwtOptions.Value;
                bearer.MapInboundClaims = false;
                bearer.TokenValidationParameters = new TokenValidationParameters
                {
                    ValidIssuer = jwt.Issuer,
                    ValidAudience = jwt.Audience,
                    IssuerSigningKey = TokenService.CreateSigningKey(jwt.SigningKey),
                    ClockSkew = TimeSpan.FromSeconds(30),
                };
                bearer.Events = new JwtBearerEvents
                {
                    OnMessageReceived = context =>
                    {
                        context.Token ??= context.Request.Cookies[AuthEndpoints.SessionCookieName];
                        return Task.CompletedTask;
                    },
                };
            });

        services.AddAuthorization();
        return services;
    }
}
