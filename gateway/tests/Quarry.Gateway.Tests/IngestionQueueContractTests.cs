using System.Text.Json;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;
using Quarry.Gateway.Infrastructure.Messaging;
using RabbitMQ.Client;
using Testcontainers.RabbitMq;

namespace Quarry.Gateway.Tests;

public sealed class IngestionQueueContractTests : IAsyncLifetime
{
    private readonly RabbitMqContainer _rabbitMq = new RabbitMqBuilder("rabbitmq:4.3-alpine").Build();

    public Task InitializeAsync() => _rabbitMq.StartAsync();

    public Task DisposeAsync() => _rabbitMq.DisposeAsync().AsTask();

    [Fact]
    public async Task EnqueueAsync_PublishesPersistentJsonJobWithDocumentIdForWorker()
    {
        var options = Options.Create(new RabbitMqOptions { Url = _rabbitMq.GetConnectionString() });
        await using var queue = new RabbitMqIngestionQueue(options, NullLogger<RabbitMqIngestionQueue>.Instance);
        var documentId = Guid.NewGuid();

        var accepted = await queue.EnqueueAsync(documentId, CancellationToken.None);

        Assert.True(accepted);
        var factory = new ConnectionFactory { Uri = new Uri(_rabbitMq.GetConnectionString()) };
        await using var connection = await factory.CreateConnectionAsync();
        await using var channel = await connection.CreateChannelAsync();
        var message = await channel.BasicGetAsync("ingest", autoAck: true);
        Assert.NotNull(message);
        Assert.True(message.BasicProperties.Persistent);
        using var json = JsonDocument.Parse(message.Body);
        Assert.Equal(documentId, json.RootElement.GetProperty("document_id").GetGuid());
    }

    [Fact]
    public async Task EnqueueAsync_WhenBrokerIsUnreachable_ReturnsFalse()
    {
        var options = Options.Create(new RabbitMqOptions { Url = "amqp://guest:guest@127.0.0.1:1" });
        await using var queue = new RabbitMqIngestionQueue(options, NullLogger<RabbitMqIngestionQueue>.Instance);

        var accepted = await queue.EnqueueAsync(Guid.NewGuid(), CancellationToken.None);

        Assert.False(accepted);
    }
}
