using System.Security.Cryptography;
using System.Text;
using Microsoft.AspNetCore.Http.HttpResults;
using Microsoft.Extensions.Options;

namespace Quarry.Gateway.Features.Auth;

internal sealed record LoginRequest(string Email, string Password);

internal sealed record UserResponse(string Email, Guid TenantId);

internal static class AuthEndpoints
{
    public const string SessionCookieName = "quarry_session";

    public static IEndpointRouteBuilder MapAuthEndpoints(this IEndpointRouteBuilder routes)
    {
        var group = routes.MapGroup("/api/auth");
        group.MapPost("/login", Login).AllowAnonymous();
        group.MapPost("/logout", Logout).AllowAnonymous();
        group.MapGet("/me", Me).RequireAuthorization();
        return routes;
    }

    private static Results<Ok<UserResponse>, ProblemHttpResult> Login(
        LoginRequest request,
        HttpContext context,
        IOptions<AuthOptions> authOptions,
        TokenService tokens)
    {
        var options = authOptions.Value;
        var emailMatches = string.Equals(request.Email?.Trim(), options.DevUserEmail, StringComparison.OrdinalIgnoreCase);
        var passwordMatches = CryptographicOperations.FixedTimeEquals(
            Encoding.UTF8.GetBytes(request.Password ?? string.Empty),
            Encoding.UTF8.GetBytes(options.DevUserPassword));

        if (!emailMatches || !passwordMatches)
        {
            return TypedResults.Problem(
                title: "E-posta veya şifre hatalı.", statusCode: StatusCodes.Status401Unauthorized);
        }

        var user = new CurrentUser(options.DevUserEmail, options.TenantId);
        var token = tokens.Issue(user);
        context.Response.Cookies.Append(SessionCookieName, token.Value, new CookieOptions
        {
            HttpOnly = true,
            Secure = true,
            SameSite = SameSiteMode.Strict,
            Path = "/",
            Expires = token.ExpiresAt,
        });
        return TypedResults.Ok(new UserResponse(user.UserId, user.TenantId));
    }

    private static NoContent Logout(HttpContext context)
    {
        context.Response.Cookies.Delete(SessionCookieName, new CookieOptions
        {
            HttpOnly = true,
            Secure = true,
            SameSite = SameSiteMode.Strict,
            Path = "/",
        });
        return TypedResults.NoContent();
    }

    private static UserResponse Me(HttpContext context)
    {
        var user = CurrentUser.Required(context.User);
        return new UserResponse(user.UserId, user.TenantId);
    }
}
