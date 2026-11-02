using System.Net.Http.Json;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Quarry.Gateway.Infrastructure.AiService;

namespace Quarry.Gateway.Tests;

internal sealed class FakeAiServiceClient(bool isReady = true, bool acceptsIngestion = true) : IAiServiceClient
{
    public List<Guid> IngestionRequests { get; } = [];

    public Task<bool> IsReadyAsync(CancellationToken cancellationToken) => Task.FromResult(isReady);

    public Task<bool> RequestIngestionAsync(Guid documentId, CancellationToken cancellationToken)
    {
        IngestionRequests.Add(documentId);
        return Task.FromResult(acceptsIngestion);
    }
}

internal sealed class GatewayFactory : WebApplicationFactory<Program>
{
    public const string UserEmail = "admin@quarry.local";
    public const string UserPassword = "correct-horse-battery";
    public static readonly Guid TenantId = Guid.Parse("00000000-0000-0000-0000-000000000001");

    private readonly string _connectionString;

    public GatewayFactory(FakeAiServiceClient? aiService = null, string? connectionString = null)
    {
        AiService = aiService ?? new FakeAiServiceClient();
        _connectionString = connectionString ?? "Host=unused;Database=unused";
        UploadsPath = Directory.CreateTempSubdirectory("quarry-uploads-").FullName;
    }

    public FakeAiServiceClient AiService { get; }

    public string UploadsPath { get; }

    public HttpClient CreateHttpsClient() =>
        CreateClient(new WebApplicationFactoryClientOptions { BaseAddress = new Uri("https://localhost") });

    public async Task<HttpClient> CreateAuthenticatedClientAsync()
    {
        var client = CreateHttpsClient();
        using var response = await client.PostAsJsonAsync(
            new Uri("/api/auth/login", UriKind.Relative), new { email = UserEmail, password = UserPassword });
        response.EnsureSuccessStatusCode();
        return client;
    }

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.UseSetting("ConnectionStrings:Quarry", _connectionString);
        builder.UseSetting("Auth:DevUserEmail", UserEmail);
        builder.UseSetting("Auth:DevUserPassword", UserPassword);
        builder.UseSetting("Jwt:SigningKey", "test-signing-key-that-is-long-enough-for-hs256");
        builder.UseSetting("AiService:BaseUrl", "http://ai.test");
        builder.UseSetting("AiService:InternalToken", "test-internal-token");
        builder.UseSetting("Storage:UploadsPath", UploadsPath);
        builder.ConfigureServices(services =>
        {
            services.RemoveAll<IAiServiceClient>();
            services.AddSingleton<IAiServiceClient>(AiService);
        });
    }

    protected override void Dispose(bool disposing)
    {
        base.Dispose(disposing);
        if (disposing && Directory.Exists(UploadsPath))
        {
            Directory.Delete(UploadsPath, recursive: true);
        }
    }
}
