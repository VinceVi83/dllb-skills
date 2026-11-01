Pick the best candidate for ONE field. Strict JSON only.

Field: REPLACE_FIELD

NEVER select a candidate whose value matches, or is closely related to, any of
these personal values (name, email, phone, address, or handle of the user):
REPLACE_FORBIDDEN

Candidates (index starts at 0):
REPLACE_CANDIDATES

Pick the candidate that best matches the field.
Prefer the most specific candidate over a vague one.
Only reject (selected = null) if:
  - the list is empty
  - the candidate is EXACTLY the full input text, verbatim
  - the candidate matches or is closely related to one of the personal values above
  - no candidate has any relation to the field

Do NOT reject a candidate just because it also contains words belonging to
another field. Partial overlap is acceptable.

Return:
{"selected": <int|null>, "confidence": <0.0-1.0>, "reason": "..."}