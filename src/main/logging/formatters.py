import json
import logging

from opentelemetry import trace


class OTelJSONFormatter(logging.Formatter):
    """JSON formatter with trace context"""

    def format(self, record):
        log_data = {
            "time": self.formatTime(record, self.datefmt),
            "name": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
        }

        # Add trace context if available
        span = trace.get_current_span()
        if span and span.is_recording():
            ctx = span.get_span_context()
            if ctx.is_valid:
                log_data["trace_id"] = format(ctx.trace_id, "032x")
                log_data["span_id"] = format(ctx.span_id, "016x")

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


class OTelHumanFormatter(logging.Formatter):
    """Human-readable formatter with trace context"""

    def format(self, record):
        # Get trace context
        trace_info = ""
        span = trace.get_current_span()
        if span and span.is_recording():
            ctx = span.get_span_context()
            if ctx.is_valid:
                trace_id = format(ctx.trace_id, "032x")
                span_id = format(ctx.span_id, "016x")
                trace_info = f" [trace_id={trace_id[:16]} span_id={span_id[:8]}]"

        # Format the main message
        log_msg = f"{self.formatTime(record)} [{record.levelname}] {record.name}{trace_info} - {record.getMessage()}"

        # Add exception if present
        if record.exc_info:
            log_msg += "\n" + self.formatException(record.exc_info)

        return log_msg
