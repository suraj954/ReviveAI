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

  useEffect(() => {
    if (!recoveryToken) {
      return undefined;
    }

    let active = true;

    async function checkRecoveryStatus() {
      try {
        const data = await getRecoveryStatus(recoveryToken);

        if (!active) {
          return;
        }

        setStatus(data.status);
        setError("");

        if (data.status === "recovery_available") {
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
          }

          onRecoveryAvailable(data.checkout);
        }

        if (
          data.status === "resolved" ||
          data.status === "unavailable"
        ) {
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
          }
        }
      } catch (err) {
        if (!active) {
          return;
        }

        if (err.message.includes("expired")) {
          setStatus("expired");
        } else {
          setError(
            "Unable to check recovery status. Retrying..."
          );
        }
      }
    }

    checkRecoveryStatus();

    intervalRef.current = setInterval(
      checkRecoveryStatus,
      POLLING_INTERVAL
    );

    return () => {
      active = false;

      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [recoveryToken, onRecoveryAvailable]);

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