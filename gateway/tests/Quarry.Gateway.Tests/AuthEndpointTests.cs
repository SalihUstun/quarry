using System.Net;
using System.Net.Http.Json;

namespace Quarry.Gateway.Tests;

public sealed class AuthEndpointTests
{
    private sealed record UserResponse(string Email, Guid TenantId);

    private static readonly Uri LoginUri = new("/api/auth/login", UriKind.Relative);
    private static readonly Uri MeUri = new("/api/auth/me", UriKind.Relative);

    [Fact]
    public async Task Login_WithValidCredentials_SetsHttpOnlyStrictSessionCookie()
    {
        await using var factory = new GatewayFactory();
        using var client = factory.CreateHttpsClient();

        using var response = await client.PostAsJsonAsync(
            LoginUri, new { email = GatewayFactory.UserEmail, password = GatewayFactory.UserPassword });

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var cookie = Assert.Single(response.Headers.GetValues("Set-Cookie"));
        Assert.StartsWith("quarry_session=", cookie, StringComparison.Ordinal);
        Assert.Contains("httponly", cookie, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("secure", cookie, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("samesite=strict", cookie, StringComparison.OrdinalIgnoreCase);
    }

    [Theory]
    [InlineData(GatewayFactory.UserEmail, "wrong-password")]
    [InlineData("someone@else.com", GatewayFactory.UserPassword)]
    public async Task Login_WithInvalidCredentials_ReturnsUnauthorized(string email, string password)
    {
        await using var factory = new GatewayFactory();
        using var client = factory.CreateHttpsClient();

        using var response = await client.PostAsJsonAsync(LoginUri, new { email, password });

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
        Assert.False(response.Headers.Contains("Set-Cookie"));
    }

    [Fact]
    public async Task Me_WithoutSession_ReturnsUnauthorized()
    {
        await using var factory = new GatewayFactory();
        using var client = factory.CreateHttpsClient();

        using var response = await client.GetAsync(MeUri);

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task Me_WithSession_ReturnsUserAndTenant()
    {
        await using var factory = new GatewayFactory();
        using var client = await factory.CreateAuthenticatedClientAsync();

        var user = await client.GetFromJsonAsync<UserResponse>(MeUri);

        Assert.Equal(new UserResponse(GatewayFactory.UserEmail, GatewayFactory.TenantId), user);
    }

    [Fact]
    public async Task Logout_ClearsSession()
    {
        await using var factory = new GatewayFactory();
        using var client = await factory.CreateAuthenticatedClientAsync();

        using var logout = await client.PostAsync(new Uri("/api/auth/logout", UriKind.Relative), content: null);
        using var me = await client.GetAsync(MeUri);

        Assert.Equal(HttpStatusCode.NoContent, logout.StatusCode);
        Assert.Equal(HttpStatusCode.Unauthorized, me.StatusCode);
    }
}
