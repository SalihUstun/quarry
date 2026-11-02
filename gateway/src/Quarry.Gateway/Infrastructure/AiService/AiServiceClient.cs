namespace Quarry.Gateway.Infrastructure.AiService;

internal interface IAiServiceClient
{
    Task<bool> IsReadyAsync(CancellationToken cancellationToken);

    Task<bool> RequestIngestionAsync(Guid documentId, CancellationToken cancellationToken);
}

internal sealed partial class AiServiceClient(HttpClient httpClient, ILogger<AiServiceClient> logger) : IAiServiceClient
{
    public async Task<bool> IsReadyAsync(CancellationToken cancellationToken)
    {
        try
        {
            using var response = await httpClient.GetAsync(new Uri("/health/ready", UriKind.Relative), cancellationToken);
            return response.IsSuccessStatusCode;
        }
        catch (Exception exception) when (exception is HttpRequestException or TaskCanceledException)
        {
            LogReadinessCheckFailed(logger, exception);
            return false;
        }
    }

    public async Task<bool> RequestIngestionAsync(Guid documentId, CancellationToken cancellationToken)
    {
        try
        {
            using var response = await httpClient.PostAsync(
                new Uri($"/internal/documents/{documentId}/ingest", UriKind.Relative), content: null, cancellationToken);
            return response.IsSuccessStatusCode;
        }
        catch (Exception exception) when (exception is HttpRequestException or TaskCanceledException)
        {
            LogIngestionRequestFailed(logger, exception, documentId);
            return false;
        }
    }

    [LoggerMessage(Level = LogLevel.Warning, Message = "AI service readiness check failed")]
    private static partial void LogReadinessCheckFailed(ILogger logger, Exception exception);

    [LoggerMessage(Level = LogLevel.Error, Message = "Ingestion request for document {DocumentId} failed")]
    private static partial void LogIngestionRequestFailed(ILogger logger, Exception exception, Guid documentId);
}
