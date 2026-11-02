FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src
COPY global.json Directory.Build.props ./
COPY src/Quarry.Gateway/Quarry.Gateway.csproj src/Quarry.Gateway/
RUN dotnet restore src/Quarry.Gateway/Quarry.Gateway.csproj
COPY src/ src/
RUN dotnet publish src/Quarry.Gateway/Quarry.Gateway.csproj -c Release -o /app --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS runtime
WORKDIR /app
COPY --from=build /app ./
USER $APP_UID
EXPOSE 8080
ENTRYPOINT ["dotnet", "Quarry.Gateway.dll"]
