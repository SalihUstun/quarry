namespace Quarry.Gateway.Infrastructure.AiService;

internal interface IAiServiceClient
{
    Task<bool> IsReadyAsync(CancellationToken cancellationToken);
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

    [LoggerMessage(Level = LogLevel.Warning, Message = "AI service readiness check failed")]
    private static partial void LogReadinessCheckFailed(ILogger logger, Exception exception);
}
