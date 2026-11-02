using System.Net;
using System.Net.Http.Json;

namespace Quarry.Gateway.Tests;

public sealed class StatusEndpointTests
{
    private sealed record StatusResponse(string Gateway, string Ai);

    [Fact]
    public async Task Health_ReturnsOk()
    {
        await using var factory = new GatewayFactory();
        using var client = factory.CreateClient();

        using var response = await client.GetAsync(new Uri("/health", UriKind.Relative));

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }

    [Theory]
    [InlineData(true, "ok")]
    [InlineData(false, "unavailable")]
    public async Task Status_ReflectsAiServiceReadiness(bool aiReady, string expectedAiStatus)
    {
        await using var factory = new GatewayFactory(new FakeAiServiceClient(isReady: aiReady));
        using var client = factory.CreateClient();

        var status = await client.GetFromJsonAsync<StatusResponse>(new Uri("/api/status", UriKind.Relative));

        Assert.NotNull(status);
        Assert.Equal("ok", status.Gateway);
        Assert.Equal(expectedAiStatus, status.Ai);
    }
}
