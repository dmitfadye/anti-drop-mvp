# Legacy MVP design migration

The user authorized applying the already approved blue visual direction to the existing static/index.html functionality. This extends the original Stage 1 scope using that established concept. The original HTML and Python backend are preserved.

Implemented sections: synthetic transaction scenarios and explainable scoring; alerts in seven languages; educational stories and five-question server-graded quiz; phone-change confirmation simulation. Next rewrites /api/* to the local FastAPI server, default http://127.0.0.1:8000, optionally configured via server-only BACKEND_URL before build.

Transactions are loaded explicitly; risk is absent before analysis. Changing scenario or language invalidates old analysis. Errors and loading states are visible; retries are possible. React renders response text without HTML insertion. Support does not create a real ticket or freeze funds. Cashback and phone changes are clearly described as demonstrations; SMS is not sent. Synthetic sample values are labeled as such. No new libraries were added.

Validation includes real backend integration for ordinary/risky scenarios, English alert, support disclaimer, quiz grading, rejected/accepted phone confirmation, and mocked network failure with a real retry. Responsive shell checks cover 390/768/1024/1440; an additional loaded mobile test checks overflow with transactions, alert and quiz present. Legacy tests remain applicable because backend source is unchanged.
