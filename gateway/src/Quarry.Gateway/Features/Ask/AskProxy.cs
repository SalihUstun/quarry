using Microsoft.Extensions.Options;
using Microsoft.Net.Http.Headers;
using Quarry.Gateway.Features.Auth;
using Quarry.Gateway.Infrastructure.AiService;
using Yarp.ReverseProxy.Configuration;
using Yarp.ReverseProxy.Transforms;

namespace Quarry.Gateway.Features.Ask;

internal static class AskProxy
{
    public const string TenantIdHeader = "X-Tenant-Id";
    public const string UserIdHeader = "X-User-Id";
    private const string ClusterId = "ai";

    private static readonly string[] StrippedHeaders =
    [
        TenantIdHeader,
        UserIdHeader,
        AiServiceOptions.InternalTokenHeader,
        HeaderNames.Cookie,
        HeaderNames.Authorization,
    ];

    public static IServiceCollection AddAskProxy(this IServiceCollection services, IConfiguration configuration)
    {
        var aiBaseUrl = configuration[$"{AiServiceOptions.SectionName}:BaseUrl"] ?? string.Empty;

        services.AddReverseProxy()
            .LoadFromMemory(
                [
                    new RouteConfig
                    {
                        RouteId = "ask",
                        ClusterId = ClusterId,
                        AuthorizationPolicy = "default",
                        Match = new RouteMatch { Path = "/api/ask", Methods = ["POST"] },
                        Transforms = [new Dictionary<string, string> { ["PathSet"] = "/ask" }],
                    },
                ],
                [
                    new ClusterConfig
                    {
                        ClusterId = ClusterId,
                        Destinations = new Dictionary<string, DestinationConfig>
                        {
                            ["ai"] = new() { Address = aiBaseUrl },
                        },
                        HttpRequest = new() { ActivityTimeout = TimeSpan.FromMinutes(5) },
                    },
                ])
            .AddTransforms(context =>
            {
                var internalToken = context.Services.GetRequiredService<IOptions<AiServiceOptions>>().Value.InternalToken;
                context.AddRequestTransform(transform =>
                {
                    ApplyIdentityHeaders(transform.ProxyRequest, transform.HttpContext.User, internalToken);
                    return ValueTask.CompletedTask;
                });
            });

        return services;
    }

    public static void ApplyIdentityHeaders(
        HttpRequestMessage proxyRequest, System.Security.Claims.ClaimsPrincipal principal, string internalToken)
    {
        foreach (var header in StrippedHeaders)
        {
            proxyRequest.Headers.Remove(header);
        }

        var user = CurrentUser.Required(principal);
        proxyRequest.Headers.Add(TenantIdHeader, user.TenantId.ToString());
        proxyRequest.Headers.Add(UserIdHeader, user.UserId);
        proxyRequest.Headers.Add(AiServiceOptions.InternalTokenHeader, internalToken);
    }
}
