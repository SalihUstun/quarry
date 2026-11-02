using System.ComponentModel.DataAnnotations;
using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.Extensions.Options;
using RabbitMQ.Client;

namespace Quarry.Gateway.Infrastructure.Messaging;

internal sealed class RabbitMqOptions
{
    public const string SectionName = "RabbitMq";

    [Required]
    public string Url { get; init; } = string.Empty;

    [Required]
    public string IngestQueue { get; init; } = "ingest";
}

internal sealed record IngestJob([property: JsonPropertyName("document_id")] Guid DocumentId);

internal interface IIngestionQueue
{
    Task<bool> EnqueueAsync(Guid documentId, CancellationToken cancellationToken);
}

internal sealed partial class RabbitMqIngestionQueue(
    IOptions<RabbitMqOptions> options,
    ILogger<RabbitMqIngestionQueue> logger) : IIngestionQueue, IAsyncDisposable
{
    private static readonly CreateChannelOptions ConfirmedChannel = new(
        publisherConfirmationsEnabled: true,
        publisherConfirmationTrackingEnabled: true);

    private readonly RabbitMqOptions _options = options.Value;
    private readonly SemaphoreSlim _connectionLock = new(1, 1);
    private IConnection? _connection;

    public async Task<bool> EnqueueAsync(Guid documentId, CancellationToken cancellationToken)
    {
        try
        {
            var connection = await GetConnectionAsync(cancellationToken);
            await using var channel = await connection.CreateChannelAsync(ConfirmedChannel, cancellationToken);
            await channel.QueueDeclareAsync(
                _options.IngestQueue, durable: true, exclusive: false, autoDelete: false, cancellationToken: cancellationToken);

            var body = JsonSerializer.SerializeToUtf8Bytes(new IngestJob(documentId));
            var properties = new BasicProperties { Persistent = true, ContentType = "application/json" };
            await channel.BasicPublishAsync(
                exchange: string.Empty,
                routingKey: _options.IngestQueue,
                mandatory: true,
                basicProperties: properties,
                body: body,
                cancellationToken: cancellationToken);
            return true;
        }
        catch (Exception exception) when (exception is not OperationCanceledException)
        {
            LogPublishFailed(logger, exception, documentId);
            return false;
        }
    }

    public async ValueTask DisposeAsync()
    {
        if (_connection is not null)
        {
            await _connection.DisposeAsync();
        }

        _connectionLock.Dispose();
    }

    private async Task<IConnection> GetConnectionAsync(CancellationToken cancellationToken)
    {
        if (_connection is { IsOpen: true })
        {
            return _connection;
        }

        await _connectionLock.WaitAsync(cancellationToken);
        try
        {
            if (_connection is { IsOpen: true })
            {
                return _connection;
            }

            if (_connection is not null)
            {
                await _connection.DisposeAsync();
            }

            var factory = new ConnectionFactory { Uri = new Uri(_options.Url), ClientProvidedName = "quarry-gateway" };
            _connection = await factory.CreateConnectionAsync(cancellationToken);
            return _connection;
        }
        finally
        {
            _connectionLock.Release();
        }
    }

    [LoggerMessage(Level = LogLevel.Error, Message = "Could not enqueue ingestion for document {DocumentId}")]
    private static partial void LogPublishFailed(ILogger logger, Exception exception, Guid documentId);
}

internal static class MessagingRegistration
{
    public static IServiceCollection AddIngestionQueue(this IServiceCollection services)
    {
        services.AddOptions<RabbitMqOptions>()
            .BindConfiguration(RabbitMqOptions.SectionName)
            .ValidateDataAnnotations()
            .ValidateOnStart();
        services.AddSingleton<IIngestionQueue, RabbitMqIngestionQueue>();
        return services;
    }
}
