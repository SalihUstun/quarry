using System.Net;
using System.Net.Http.Json;
using System.Security.Claims;
using Quarry.Gateway.Features.Ask;
using Quarry.Gateway.Features.Auth;

namespace Quarry.Gateway.Tests;

public sealed class AskProxyTests
{
    [Fact]
    public void ApplyIdentityHeaders_ReplacesSpoofedHeadersWithAuthenticatedIdentity()
    {
        var tenantId = Guid.NewGuid();
        var principal = new ClaimsPrincipal(new ClaimsIdentity(
            [new Claim("sub", "ayse@ornek.com"), new Claim(CurrentUser.TenantIdClaim, tenantId.ToString())],
            authenticationType: "test"));
        using var request = new HttpRequestMessage(HttpMethod.Post, "http://ai.test/ask");
        request.Headers.Add("X-Tenant-Id", Guid.NewGuid().ToString());
        request.Headers.Add("X-User-Id", "saldirgan@kotu.com");
        request.Headers.Add("X-Internal-Token", "guessed-token");
        request.Headers.Add("Cookie", "quarry_session=secret-jwt");

        AskProxy.ApplyIdentityHeaders(request, principal, "real-internal-token");

        Assert.Equal([tenantId.ToString()], request.Headers.GetValues("X-Tenant-Id"));
        Assert.Equal(["ayse@ornek.com"], request.Headers.GetValues("X-User-Id"));
        Assert.Equal(["real-internal-token"], request.Headers.GetValues("X-Internal-Token"));
        Assert.False(request.Headers.Contains("Cookie"));
    }

    [Fact]
    public async Task Ask_WithoutSession_ReturnsUnauthorized()
    {
        await using var factory = new GatewayFactory();
        using var client = factory.CreateHttpsClient();

        using var response = await client.PostAsJsonAsync(
            new Uri("/api/ask", UriKind.Relative), new { question = "İzin kaç gün?" });

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }
}
