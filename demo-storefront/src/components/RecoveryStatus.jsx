import { useEffect, useRef, useState } from "react";
import { getRecoveryStatus } from "../services/api";

const POLLING_INTERVAL = 3000;

function RecoveryStatus({
  product,
  recoveryToken,
  onRecoveryAvailable,
}) {
  const [status, setStatus] = useState("pending");
  const [error, setError] = useState("");

  const intervalRef = useRef(null);
  const recoveryFoundRef = useRef(false);
  const callbackRef = useRef(onRecoveryAvailable);
  const requestInProgressRef = useRef(false);

  // Always keep the latest callback without restarting polling.
  useEffect(() => {
    callbackRef.current = onRecoveryAvailable;
  }, [onRecoveryAvailable]);

  useEffect(() => {
    if (!recoveryToken) {
      return undefined;
    }

    let active = true;

    // Reset only when a NEW recovery token/session starts.
    recoveryFoundRef.current = false;
    requestInProgressRef.current = false;

    setStatus("pending");
    setError("");

    const stopPolling = () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };

    async function checkRecoveryStatus() {
      // Never poll again after recovery has been found.
      if (
        recoveryFoundRef.current ||
        requestInProgressRef.current
      ) {
        return;
      }

      requestInProgressRef.current = true;

      try {
        const data = await getRecoveryStatus(recoveryToken);

        if (
          !active ||
          recoveryFoundRef.current
        ) {
          return;
        }

        setError("");

        // ---------------------------------------------
        // Recovery is available
        // Lock this state permanently for this session.
        // ---------------------------------------------
        if (data.status === "recovery_available") {
          recoveryFoundRef.current = true;

          setStatus("recovery_available");

          stopPolling();

          if (callbackRef.current) {
            callbackRef.current(data.checkout);
          }

          return;
        }

        // ---------------------------------------------
        // Terminal states
        // ---------------------------------------------
        if (
          data.status === "resolved" ||
          data.status === "unavailable"
        ) {
          setStatus(data.status);
          stopPolling();
          return;
        }

        // ---------------------------------------------
        // Normal pending state
        // ---------------------------------------------
        setStatus(data.status || "pending");

      } catch (err) {
        if (!active) {
          return;
        }

        if (
          err.message &&
          err.message.toLowerCase().includes("expired")
        ) {
          setStatus("expired");
          stopPolling();
        } else {
          setError(
            "Unable to check recovery status. Retrying..."
          );
        }
      } finally {
        requestInProgressRef.current = false;
      }
    }

    // Check immediately.
    checkRecoveryStatus();

    // Continue polling.
    intervalRef.current = setInterval(
      checkRecoveryStatus,
      POLLING_INTERVAL
    );

    return () => {
      active = false;
      stopPolling();
      requestInProgressRef.current = false;
    };
  }, [recoveryToken]);

  const content = {
    pending: {
      title: "ReviveAI is analyzing your payment",
      description:
        "Our recovery engine is securely evaluating the best next step.",
      stateClass: "status-pending",
    },

    recovery_available: {
      title: "Recovery option available",
      description:
        "ReviveAI found a safe path to retry your payment.",
      stateClass: "status-available",
    },

    resolved: {
      title: "Payment successfully recovered",
      description:
        "Your payment recovery workflow has been completed.",
      stateClass: "status-resolved",
    },

    unavailable: {
      title: "Recovery is not available",
      description:
        "No additional recovery action can be safely performed.",
      stateClass: "status-unavailable",
    },

    expired: {
      title: "Recovery session expired",
      description:
        "For your security, this recovery session is no longer active.",
      stateClass: "status-expired",
    },
  };

  const current = content[status] || content.pending;

  return (
    <section className={`recovery-status ${current.stateClass}`}>
      <div className="recovery-status-header">
        <div className="recovery-pulse">
          <span />
          <span />
          <span />
        </div>

        <div>
          <p className="recovery-label">
            REVIVEAI RECOVERY ENGINE
          </p>

          <h2>{current.title}</h2>
        </div>
      </div>

      <p className="recovery-description">
        {current.description}
      </p>

      {product && (
        <div className="recovery-product">
          <span>Order</span>
          <strong>{product.name}</strong>
        </div>
      )}

      {error && (
        <p className="recovery-error">
          {error}
        </p>
      )}

      {status === "pending" && (
        <div className="recovery-progress">
          <div className="progress-bar">
            <span />
          </div>

          <p>
            Monitoring payment recovery in real time
          </p>
        </div>
      )}
    </section>
  );
}

export default RecoveryStatus;