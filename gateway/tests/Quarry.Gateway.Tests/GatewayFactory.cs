using System.Net.Http.Json;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Quarry.Gateway.Infrastructure.AiService;
using Quarry.Gateway.Infrastructure.Messaging;

namespace Quarry.Gateway.Tests;

internal sealed class FakeAiServiceClient(bool isReady = true) : IAiServiceClient
{
    public Task<bool> IsReadyAsync(CancellationToken cancellationToken) => Task.FromResult(isReady);
}

internal sealed class FakeIngestionQueue(bool accepts = true) : IIngestionQueue
{
    public List<Guid> Enqueued { get; } = [];

    public Task<bool> EnqueueAsync(Guid documentId, CancellationToken cancellationToken)
    {
        Enqueued.Add(documentId);
        return Task.FromResult(accepts);
    }
}

internal sealed class GatewayFactory : WebApplicationFactory<Program>
{
    public const string UserEmail = "admin@quarry.local";
    public const string UserPassword = "correct-horse-battery";
    public static readonly Guid TenantId = Guid.Parse("00000000-0000-0000-0000-000000000001");

    private readonly string _connectionString;

    public GatewayFactory(
        FakeAiServiceClient? aiService = null,
        string? connectionString = null,
        FakeIngestionQueue? ingestionQueue = null)
    {
        AiService = aiService ?? new FakeAiServiceClient();
        IngestionQueue = ingestionQueue ?? new FakeIngestionQueue();
        _connectionString = connectionString ?? "Host=unused;Database=unused";
        UploadsPath = Directory.CreateTempSubdirectory("quarry-uploads-").FullName;
    }

    public FakeAiServiceClient AiService { get; }

    public FakeIngestionQueue IngestionQueue { get; }

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
        builder.UseSetting("RabbitMq:Url", "amqp://guest:guest@rabbitmq.test:5672");
        builder.ConfigureServices(services =>
        {
            services.RemoveAll<IAiServiceClient>();
            services.AddSingleton<IAiServiceClient>(AiService);
            services.RemoveAll<IIngestionQueue>();
            services.AddSingleton<IIngestionQueue>(IngestionQueue);
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
