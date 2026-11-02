using Npgsql;
using Testcontainers.PostgreSql;

namespace Quarry.Gateway.Tests;

public sealed class PostgresFixture : IAsyncLifetime
{
    private const string UpMarker = "-- migrate:up";
    private const string DownMarker = "-- migrate:down";

    private readonly PostgreSqlContainer _container = new PostgreSqlBuilder("pgvector/pgvector:0.8.7-pg17").Build();

    public string ConnectionString => _container.GetConnectionString();

    public async Task InitializeAsync()
    {
        await _container.StartAsync();
        await using var connection = new NpgsqlConnection(ConnectionString);
        await connection.OpenAsync();
        foreach (var migration in Directory.GetFiles(FindMigrationsDirectory(), "*.sql").Order(StringComparer.Ordinal))
        {
            var upSection = (await File.ReadAllTextAsync(migration)).Split(DownMarker)[0].Replace(UpMarker, string.Empty, StringComparison.Ordinal);
            await using var command = new NpgsqlCommand(upSection, connection);
            await command.ExecuteNonQueryAsync();
        }
    }

    public Task DisposeAsync() => _container.DisposeAsync().AsTask();

    public async Task ExecuteAsync(string sql, params object[] parameters)
    {
        await using var connection = new NpgsqlConnection(ConnectionString);
        await connection.OpenAsync();
        await using var command = new NpgsqlCommand(sql, connection);
        foreach (var parameter in parameters)
        {
            command.Parameters.Add(new NpgsqlParameter { Value = parameter });
        }

        await command.ExecuteNonQueryAsync();
    }

    public async Task<T?> ScalarAsync<T>(string sql, params object[] parameters)
    {
        await using var connection = new NpgsqlConnection(ConnectionString);
        await connection.OpenAsync();
        await using var command = new NpgsqlCommand(sql, connection);
        foreach (var parameter in parameters)
        {
            command.Parameters.Add(new NpgsqlParameter { Value = parameter });
        }

        return (T?)await command.ExecuteScalarAsync();
    }

    private static string FindMigrationsDirectory()
    {
        for (var directory = new DirectoryInfo(AppContext.BaseDirectory); directory is not null; directory = directory.Parent)
        {
            var candidate = Path.Combine(directory.FullName, "db", "migrations");
            if (Directory.Exists(candidate))
            {
                return candidate;
            }
        }

        throw new DirectoryNotFoundException("db/migrations directory not found above test output");
    }
}

[CollectionDefinition(Name)]
public sealed class PostgresTestGroup : ICollectionFixture<PostgresFixture>
{
    public const string Name = "postgres";
}
