using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Quarry.Gateway.Infrastructure.AiService;

namespace Quarry.Gateway.Tests;

internal sealed class FakeAiServiceClient(bool isReady) : IAiServiceClient
{
    public Task<bool> IsReadyAsync(CancellationToken cancellationToken) => Task.FromResult(isReady);
}

internal sealed class GatewayFactory(bool aiReady) : WebApplicationFactory<Program>
{
    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.ConfigureServices(services =>
        {
            services.RemoveAll<IAiServiceClient>();
            services.AddSingleton<IAiServiceClient>(new FakeAiServiceClient(aiReady));
        });
    }
}
