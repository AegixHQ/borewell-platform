/**
 * Web preview version: loads Razorpay's checkout.js into the page and opens
 * it (it draws its own overlay). Same onResult contract as RazorpaySheet.js.
 */
import { useEffect, useRef } from "react";
import { checkoutOptions } from "../lib/razorpay";

const SCRIPT = "https://checkout.razorpay.com/v1/checkout.js";

function loadScript() {
  if (window.Razorpay) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const tag = document.createElement("script");
    tag.src = SCRIPT;
    tag.onload = resolve;
    tag.onerror = () => reject(new Error("Could not load Razorpay."));
    document.head.appendChild(tag);
  });
}

export default function RazorpaySheet({ order, email, onResult }) {
  const started = useRef(null);

  useEffect(() => {
    if (!order) {
      started.current = null;
      return;
    }
    if (started.current === order.razorpay_order_id) return;
    started.current = order.razorpay_order_id;
    loadScript()
      .then(() => {
        const rzp = new window.Razorpay({
          ...checkoutOptions({ order, email }),
          handler: (result) => onResult({ status: "success", result }),
          modal: { ondismiss: () => onResult({ status: "dismissed" }) },
        });
        rzp.on("payment.failed", (r) =>
          onResult({ status: "failed", message: r?.error?.description || "The payment failed." })
        );
        rzp.open();
      })
      .catch((err) => onResult({ status: "failed", message: err.message }));
  }, [order, email, onResult]);

  return null;
}
