using Microsoft.EntityFrameworkCore;
using Quarry.Gateway.Features.Ask;
using Quarry.Gateway.Features.Auth;
using Quarry.Gateway.Features.Documents;
using Quarry.Gateway.Features.Status;
using Quarry.Gateway.Infrastructure.AiService;
using Quarry.Gateway.Infrastructure.Persistence;
using Quarry.Gateway.Infrastructure.Storage;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddProblemDetails();
builder.Services.AddHealthChecks();
builder.Services.AddQuarryAuth();
builder.Services.AddAiService();
builder.Services.AddAskProxy(builder.Configuration);
builder.Services.AddDbContext<QuarryDbContext>(options => options
    .UseNpgsql(builder.Configuration.GetConnectionString("Quarry"))
    .UseSnakeCaseNamingConvention());
builder.Services.AddOptions<StorageOptions>()
    .BindConfiguration(StorageOptions.SectionName)
    .ValidateDataAnnotations()
    .ValidateOnStart();
builder.Services.AddSingleton<IFileStorage, LocalFileStorage>();
builder.WebHost.ConfigureKestrel(kestrel => kestrel.Limits.MaxRequestBodySize = 60L * 1024 * 1024);

var app = builder.Build();

app.UseExceptionHandler();
app.UseAuthentication();
app.UseAuthorization();

app.MapHealthChecks("/health");
app.MapStatusEndpoints();
app.MapAuthEndpoints();
app.MapDocumentEndpoints();
app.MapReverseProxy();

app.Run();
