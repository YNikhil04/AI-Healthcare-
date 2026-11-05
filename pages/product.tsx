"use client";

import { useState, FormEvent } from "react";
import { useAuth, UserButton } from "@clerk/nextjs";
import DatePicker from "react-datepicker";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import { fetchEventSource } from "@microsoft/fetch-event-source";

function ConsultationForm() {
  const { getToken } = useAuth();

  // Form state
  const [patientName, setPatientName] = useState("");
  const [visitDate, setVisitDate] = useState<Date | null>(new Date());
  const [notes, setNotes] = useState("");

  // Streaming state
  const [output, setOutput] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setOutput("");
    setLoading(true);

    const jwt = await getToken();
    if (!jwt) {
      setOutput("Authentication required. Please sign in.");
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    let buffer = "";

    try {
      await fetchEventSource("/api/consultation", {
        signal: controller.signal,
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${jwt}`,
        },
        body: JSON.stringify({
          patient_name: patientName,
          // local date (avoids the UTC off-by-one-day issue)
          date_of_visit: visitDate
            ? `${visitDate.getFullYear()}-${String(visitDate.getMonth() + 1).padStart(2, "0")}-${String(visitDate.getDate()).padStart(2, "0")}`
            : "",
          notes,
        }),
        openWhenHidden: true,
        async onopen(response) {
          if (
            response.ok &&
            response.headers.get("content-type")?.includes("text/event-stream")
          ) {
            return;
          }
          const errorText = await response.text().catch(() => "");
          throw new Error(
            `HTTP ${response.status}: ${errorText || "Unknown server error"}`,
          );
        },
        onmessage(ev) {
          buffer += ev.data;
          setOutput(buffer);
        },
        onclose() {
          setLoading(false);
        },
        onerror(err) {
          console.error("Streaming error:", err);
          setOutput(
            `Error: ${err instanceof Error ? err.message : String(err)}`,
          );
          setLoading(false);
          controller.abort();
          throw err; // stops fetchEventSource from retrying
        },
      });
    } catch (err) {
      console.error("Fetch failed:", err);
    } finally {
      setLoading(false); // button can never get stuck
    }
  }

  return (
    <div className="container mx-auto px-4 py-12 max-w-3xl">
      <h1 className="text-4xl font-bold text-gray-900 dark:text-gray-100 mb-8">
        Consultation Notes
      </h1>

      <form
        onSubmit={handleSubmit}
        className="space-y-6 bg-white dark:bg-gray-800 rounded-xl shadow-lg p-8"
      >
        <div className="space-y-2">
          <label
            htmlFor="patient"
            className="block text-sm font-medium text-gray-700 dark:text-gray-300"
          >
            Patient Name
          </label>
          <input
            id="patient"
            type="text"
            required
            value={patientName}
            onChange={(e) => setPatientName(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
            placeholder="Enter patient's full name"
          />
        </div>

        <div className="space-y-2">
          <label
            htmlFor="date"
            className="block text-sm font-medium text-gray-700 dark:text-gray-300"
          >
            Date of Visit
          </label>
          <DatePicker
            id="date"
            selected={visitDate}
            onChange={(d: Date | null) => setVisitDate(d)}
            dateFormat="yyyy-MM-dd"
            placeholderText="Select date"
            required
            className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
          />
        </div>

        <div className="space-y-2">
          <label
            htmlFor="notes"
            className="block text-sm font-medium text-gray-700 dark:text-gray-300"
          >
            Consultation Notes
          </label>
          <textarea
            id="notes"
            required
            rows={8}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
            placeholder="Enter detailed consultation notes..."
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-semibold py-3 px-6 rounded-lg transition-colors duration-200"
        >
          {loading ? "Generating Summary..." : "Generate Summary"}
        </button>
      </form>

      {output && (
        <section className="mt-8 bg-slate-900 border border-blue-900 rounded-xl shadow-lg p-8">
          <div className="markdown-content prose prose-invert prose-headings:text-white prose-p:text-white prose-li:text-white prose-strong:text-white prose-a:text-blue-300 max-w-none text-white">
            <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
              {output}
            </ReactMarkdown>
          </div>
        </section>
      )}
    </div>
  );
}

export default function Product() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800">
      {/* User Menu in Top Right */}
      <div className="absolute top-4 right-4">
        <UserButton showName={true} />
      </div>

      <ConsultationForm />
    </main>
  );
}
