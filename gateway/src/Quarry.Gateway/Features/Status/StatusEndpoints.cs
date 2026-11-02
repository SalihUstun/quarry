using Quarry.Gateway.Infrastructure.AiService;

namespace Quarry.Gateway.Features.Status;

internal sealed record SystemStatus(string Gateway, string Ai);

internal static class StatusEndpoints
{
    public static IEndpointRouteBuilder MapStatusEndpoints(this IEndpointRouteBuilder routes)
    {
        routes.MapGet("/api/status", GetStatusAsync);
        return routes;
    }

    private static async Task<SystemStatus> GetStatusAsync(IAiServiceClient aiService, CancellationToken cancellationToken)
    {
        var aiReady = await aiService.IsReadyAsync(cancellationToken);
        return new SystemStatus(Gateway: "ok", Ai: aiReady ? "ok" : "unavailable");
    }
}
