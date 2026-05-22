from prometheus_client import Counter, Gauge

EventCount = Counter(
    "stark_event_count",
    "Number of events being processed",
    labelnames=["type"],
)
SpamPredictionStat = Counter(
    "stark_spam_prediction_stat",
    "Number of spam prediction event",
    labelnames=["status"],
)
MessageStat = Counter(
    "stark_message_stat",
    "Number of message",
    labelnames=["type"],
)
CommandCount = Counter("stark_command_stats", "Number of coomand", labelnames=["name"])
UnhandledError = Counter("stark_unhandled_error", "Number of unhandled error", labelnames=["type"])

EventLatencySecond = Gauge(
    "stark_event_latency",
    "Latency of event processed",
    labelnames=["type"],
    unit="second",
)
CommandLatencySecond = Gauge(
    "stark_command_latency",
    "Latency of command processed",
    labelnames=["name"],
    unit="second",
)
