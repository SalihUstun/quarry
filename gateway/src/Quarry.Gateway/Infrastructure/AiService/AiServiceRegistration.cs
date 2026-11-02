using Microsoft.Extensions.Options;

namespace Quarry.Gateway.Infrastructure.AiService;

internal static class AiServiceRegistration
{
    public static IServiceCollection AddAiService(this IServiceCollection services)
    {
        services.AddOptions<AiServiceOptions>()
            .BindConfiguration(AiServiceOptions.SectionName)
            .ValidateDataAnnotations()
            .ValidateOnStart();

        services.AddHttpClient<IAiServiceClient, AiServiceClient>((provider, client) =>
        {
            var options = provider.GetRequiredService<IOptions<AiServiceOptions>>().Value;
            client.BaseAddress = new Uri(options.BaseUrl);
            client.Timeout = TimeSpan.FromSeconds(options.TimeoutSeconds);
            client.DefaultRequestHeaders.Add(AiServiceOptions.InternalTokenHeader, options.InternalToken);
        });

        return services;
    }
}
