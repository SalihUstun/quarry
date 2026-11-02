use std::sync::Arc;
use std::time::Duration;

use anyhow::{Context, Result};
use futures_util::StreamExt;
use lapin::message::Delivery;
use lapin::options::{
    BasicAckOptions, BasicConsumeOptions, BasicNackOptions, BasicPublishOptions, BasicQosOptions,
    ConfirmSelectOptions, QueueDeclareOptions,
};
use lapin::types::{AMQPValue, FieldTable};
use lapin::{BasicProperties, Channel, Connection, ConnectionProperties};
use serde::{Deserialize, Serialize};
use tokio::task::JoinSet;
use tracing::{error, info, warn};
use uuid::Uuid;

use crate::config::Config;
use crate::error::ProcessError;
use crate::pipeline::{Outcome, Pipeline};

pub const INGEST_QUEUE: &str = "ingest";
pub const RETRY_QUEUE: &str = "ingest.retry";
pub const DEAD_LETTER_QUEUE: &str = "ingest.dead";
const ATTEMPT_HEADER: &str = "x-attempt";
const PERSISTENT: u8 = 2;

#[derive(Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct IngestJob {
    pub document_id: Uuid,
}

#[derive(Debug, PartialEq, Eq)]
pub enum Disposition {
    Done,
    Retry { next_attempt: u32 },
    DeadLetter,
}

#[must_use]
pub fn disposition(
    result: &Result<Outcome, ProcessError>,
    attempt: u32,
    max_attempts: u32,
) -> Disposition {
    match result {
        Ok(_) => Disposition::Done,
        Err(error) if error.is_retryable() && attempt < max_attempts => Disposition::Retry {
            next_attempt: attempt + 1,
        },
        Err(_) => Disposition::DeadLetter,
    }
}

pub async fn run(config: &Config, pipeline: Arc<Pipeline>) -> Result<()> {
    let connection = connect_with_retry(&config.amqp_url).await?;
    let channel = connection.create_channel().await?;
    channel
        .confirm_select(ConfirmSelectOptions::default())
        .await?;
    channel
        .basic_qos(config.concurrency, BasicQosOptions::default())
        .await?;
    declare_topology(&channel, config.retry_delay).await?;

    let mut consumer = channel
        .basic_consume(
            INGEST_QUEUE.into(),
            "quarry-worker".into(),
            BasicConsumeOptions::default(),
            FieldTable::default(),
        )
        .await?;
    info!(
        concurrency = config.concurrency,
        "worker is consuming ingest jobs"
    );

    let mut in_flight = JoinSet::new();
    let shutdown = shutdown_signal();
    tokio::pin!(shutdown);

    loop {
        tokio::select! {
            () = &mut shutdown => {
                info!("shutdown requested, no longer accepting new jobs");
                break;
            }
            delivery = consumer.next() => match delivery {
                Some(Ok(delivery)) => {
                    in_flight.spawn(handle_delivery(
                        delivery,
                        Arc::clone(&pipeline),
                        channel.clone(),
                        config.max_attempts,
                    ));
                }
                Some(Err(error)) => return Err(error).context("consumer stream failed"),
                None => break,
            },
            Some(joined) = in_flight.join_next(), if !in_flight.is_empty() => log_join(joined),
        }
    }

    while let Some(joined) = in_flight.join_next().await {
        log_join(joined);
    }
    info!("all in-flight jobs finished");
    Ok(())
}

fn log_join(joined: Result<(), tokio::task::JoinError>) {
    if let Err(error) = joined {
        error!(%error, "job task panicked");
    }
}

async fn connect_with_retry(url: &str) -> Result<Connection> {
    let mut attempt = 0;
    loop {
        attempt += 1;
        match Connection::connect(url, ConnectionProperties::default()).await {
            Ok(connection) => return Ok(connection),
            Err(error) if attempt < 30 => {
                warn!(%error, attempt, "RabbitMQ is not reachable yet, retrying");
                tokio::time::sleep(Duration::from_secs(2)).await;
            }
            Err(error) => return Err(error).context("could not connect to RabbitMQ"),
        }
    }
}

pub async fn declare_topology(channel: &Channel, retry_delay: Duration) -> Result<()> {
    channel
        .queue_declare(
            INGEST_QUEUE.into(),
            QueueDeclareOptions::durable(),
            FieldTable::default(),
        )
        .await?;

    let mut retry_arguments = FieldTable::default();
    retry_arguments.insert(
        "x-message-ttl".into(),
        AMQPValue::LongLongInt(i64::try_from(retry_delay.as_millis()).unwrap_or(i64::MAX)),
    );
    retry_arguments.insert(
        "x-dead-letter-exchange".into(),
        AMQPValue::LongString("".into()),
    );
    retry_arguments.insert(
        "x-dead-letter-routing-key".into(),
        AMQPValue::LongString(INGEST_QUEUE.into()),
    );
    channel
        .queue_declare(
            RETRY_QUEUE.into(),
            QueueDeclareOptions::durable(),
            retry_arguments,
        )
        .await?;

    channel
        .queue_declare(
            DEAD_LETTER_QUEUE.into(),
            QueueDeclareOptions::durable(),
            FieldTable::default(),
        )
        .await?;
    Ok(())
}

async fn handle_delivery(
    delivery: Delivery,
    pipeline: Arc<Pipeline>,
    channel: Channel,
    max_attempts: u32,
) {
    let attempt = attempt_of(&delivery.properties);
    let settled = match serde_json::from_slice::<IngestJob>(&delivery.data) {
        Ok(job) => process_job(&job, &delivery, &pipeline, &channel, attempt, max_attempts).await,
        Err(error) => {
            warn!(%error, "discarding malformed ingest message");
            publish(&channel, DEAD_LETTER_QUEUE, &delivery.data, attempt).await
        }
    };

    let acknowledgement = match settled {
        Ok(()) => delivery.ack(BasicAckOptions::default()).await,
        Err(error) => {
            error!(%error, "could not settle job, returning it to the queue");
            delivery
                .nack(BasicNackOptions {
                    requeue: true,
                    ..BasicNackOptions::default()
                })
                .await
        }
    };
    if let Err(error) = acknowledgement {
        error!(%error, "could not acknowledge delivery");
    }
}

async fn process_job(
    job: &IngestJob,
    delivery: &Delivery,
    pipeline: &Pipeline,
    channel: &Channel,
    attempt: u32,
    max_attempts: u32,
) -> Result<()> {
    let document_id = job.document_id;
    let result = pipeline.process(document_id, delivery.redelivered).await;

    match disposition(&result, attempt, max_attempts) {
        Disposition::Done => {
            match result {
                Ok(Outcome::Completed { pages, chunks }) => {
                    info!(%document_id, pages, chunks, attempt, "document processed");
                }
                Ok(Outcome::Skipped) => {
                    info!(%document_id, "document already handled, skipping");
                }
                Err(_) => {}
            }
            Ok(())
        }
        Disposition::Retry { next_attempt } => {
            let message = failure_message(&result);
            warn!(%document_id, attempt, error = %message, "processing failed, will retry");
            pipeline
                .store()
                .schedule_retry(
                    document_id,
                    &format!("Tekrar denenecek ({next_attempt}/{max_attempts}): {message}"),
                )
                .await?;
            publish(channel, RETRY_QUEUE, &delivery.data, next_attempt).await
        }
        Disposition::DeadLetter => {
            let message = failure_message(&result);
            error!(%document_id, attempt, error = %message, "processing failed permanently");
            pipeline.store().mark_failed(document_id, &message).await?;
            publish(channel, DEAD_LETTER_QUEUE, &delivery.data, attempt).await
        }
    }
}

fn failure_message(result: &Result<Outcome, ProcessError>) -> String {
    result
        .as_ref()
        .err()
        .map_or_else(String::new, ToString::to_string)
}

async fn publish(channel: &Channel, queue: &str, payload: &[u8], attempt: u32) -> Result<()> {
    let mut headers = FieldTable::default();
    headers.insert(
        ATTEMPT_HEADER.into(),
        AMQPValue::LongLongInt(attempt.into()),
    );
    let properties = BasicProperties::default()
        .with_delivery_mode(PERSISTENT)
        .with_content_type("application/json".into())
        .with_headers(headers);

    let confirmation = channel
        .basic_publish(
            "".into(),
            queue.into(),
            BasicPublishOptions::default(),
            payload,
            properties,
        )
        .await?
        .await?;
    anyhow::ensure!(
        confirmation.is_ack(),
        "broker did not confirm message to {queue}"
    );
    Ok(())
}

fn attempt_of(properties: &BasicProperties) -> u32 {
    properties
        .headers()
        .as_ref()
        .and_then(|headers| headers.inner().get(ATTEMPT_HEADER))
        .and_then(|value| match value {
            AMQPValue::LongLongInt(number) => u32::try_from(*number).ok(),
            AMQPValue::LongInt(number) => u32::try_from(*number).ok(),
            _ => None,
        })
        .unwrap_or(1)
}

async fn shutdown_signal() {
    let ctrl_c = async {
        if let Err(error) = tokio::signal::ctrl_c().await {
            error!(%error, "could not listen for ctrl-c");
        }
    };

    #[cfg(unix)]
    let terminate = async {
        match tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate()) {
            Ok(mut signal) => {
                signal.recv().await;
            }
            Err(error) => error!(%error, "could not listen for SIGTERM"),
        }
    };
    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        () = ctrl_c => {}
        () = terminate => {}
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn retryable() -> Result<Outcome, ProcessError> {
        Err(ProcessError::EmbeddingUnavailable("busy".into()))
    }

    #[test]
    fn successful_and_skipped_jobs_are_done() {
        let completed = Ok(Outcome::Completed {
            pages: 3,
            chunks: 3,
        });

        assert_eq!(disposition(&completed, 1, 5), Disposition::Done);
        assert_eq!(disposition(&Ok(Outcome::Skipped), 1, 5), Disposition::Done);
    }

    #[test]
    fn transient_failures_are_retried_until_the_last_attempt() {
        assert_eq!(
            disposition(&retryable(), 1, 5),
            Disposition::Retry { next_attempt: 2 }
        );
        assert_eq!(
            disposition(&retryable(), 4, 5),
            Disposition::Retry { next_attempt: 5 }
        );
        assert_eq!(disposition(&retryable(), 5, 5), Disposition::DeadLetter);
    }

    #[test]
    fn permanent_failures_go_straight_to_dead_letter() {
        assert_eq!(
            disposition(&Err(ProcessError::NoText), 1, 5),
            Disposition::DeadLetter
        );
    }

    #[test]
    fn attempt_header_defaults_to_first_attempt() {
        assert_eq!(attempt_of(&BasicProperties::default()), 1);

        let mut headers = FieldTable::default();
        headers.insert(ATTEMPT_HEADER.into(), AMQPValue::LongLongInt(3));
        assert_eq!(
            attempt_of(&BasicProperties::default().with_headers(headers)),
            3
        );
    }

    #[test]
    fn ingest_job_uses_document_id_json_contract() {
        let document_id = Uuid::new_v4();
        let json = format!(r#"{{"document_id":"{document_id}"}}"#);

        let job: IngestJob = serde_json::from_str(&json).expect("valid job");

        assert_eq!(job, IngestJob { document_id });
    }
}
