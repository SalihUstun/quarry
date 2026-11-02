using Quarry.Gateway.Features.Status;
using Quarry.Gateway.Infrastructure.AiService;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddHealthChecks();
builder.Services.AddAiService();

var app = builder.Build();

app.MapHealthChecks("/health");
app.MapStatusEndpoints();

app.Run();
