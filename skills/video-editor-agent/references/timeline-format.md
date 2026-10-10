# Timeline

Use the bundled assets/timeline.example.json. Paths are local, relative to the JSON or absolute. No URL inputs; download licensed sources through supported routes first.

Fields: title; width/height (even pixels); fps (integer 1–60); narration path; optional SRT captions path; shots array. Each shot has unique id, path, kind (image/video), positive duration, fit (contain/cover), preview boolean, source_url and license. Video shots can have an in offset in seconds.

Shots run consecutively. Frame boundaries use cumulative rounding to avoid drift. Source video audio is removed; narration is the continuous soundtrack. For talking-head edits, separately create the approved audio edit using the same intervals.

Use contain for cards; cover intentionally crops footage. Final validation rejects undersized assets and preview flags. --allow-preview makes a labelled draft. Repeated files and still holds over 12 seconds produce editorial warnings. License entries document provenance but don't independently verify permission.

Audio and timeline durations must match within 0.25 seconds. Adjust the last shot to measured audio; don't pad to a desired duration. No automatic B-roll looping or invented movement.

Caption bottom margin is 4% of frame height. Reserve layout space and inspect actual rendered font/readability. Captions require FFmpeg's subtitles filter; missing captions are a delivery warning.
