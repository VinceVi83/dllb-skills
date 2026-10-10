Current datetime: {now}

Decide: send NOW or LATER (if a future time is mentioned).
If LATER, give the datetime.
Clean the request: keep ONLY the message content.
Remove verb, platform, target, separator, scheduling words.

Return ONLY JSON:

{
  "tool": "send_now" | "add_oneshot_task",
  "message": "<cleaned content only>",
  "run_date": "<datetime, only if later>"
}

Examples:
"envoie un message sur discord : je vais faire les courses"
  -> {"send":"now","message":"je vais faire les courses"}

"dans 2h envoie : le repas est prêt"
  -> {"send":"delay","message":"le repas est prêt","run_date":"<now+2h>"}