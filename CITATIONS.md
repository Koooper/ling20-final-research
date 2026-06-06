# Citations

Paper-facing references for the tools and methods this pipeline depends on. Copy the relevant
entries into the manuscript's References section; the prose snippets under each are drop-in
Methods sentences. Citation style is APA-ish — reformat to the venue's house style as needed.

## Acoustic analysis software

**Praat** — all annotation, the frozen measurement battery (02), and spectrogram export.

> Boersma, P., & Weenink, D. (2024). *Praat: doing phonetics by computer* [Computer program].
> Version 6.4.x, retrieved from http://www.praat.org/

Methods: "Segmentation and acoustic measurement were carried out in Praat (Boersma & Weenink,
2024). Record the exact version you ran (Help → About Praat) — we used 6.4.x."

## Formant tracking

**FastTrack** — canonical formant estimation. Sweeps a range of LPC ceilings per vowel and
selects the smoothest track by DCT-fit error, rather than committing to a single ceiling.

> Barreda, S. (2021). Fast Track: fast (nearly) automatic formant-tracking using Praat.
> *Linguistics Vanguard, 7*(1), 20200051. https://doi.org/10.1515/lingvang-2020-0051

Plugin (vendored under `praat/vendor/FastTrack/`, MIT license): the implementation tracks the
method in Barreda (2021). Cite the paper, not the repository, for the method; note the plugin
version in a footnote if a reviewer asks for reproducibility specifics.

Methods: "Formants were estimated with the FastTrack procedure (Barreda, 2021), which analyzes
each vowel at multiple LPC ceilings and selects the analysis minimizing smoothness-penalized
prediction error. A single-ceiling Burg estimate was retained alongside for a methods comparison
(`output/{speaker}/formant_method_comparison.csv`)."

## Statistics

**SciPy** — the Welch two-tailed t-tests (`scipy.stats.ttest_ind(..., equal_var=False)`) reported
in the ejective vs non-ejective comparison.

> Virtanen, P., Gommers, R., Oliphant, T. E., et al. (2020). SciPy 1.0: fundamental algorithms
> for scientific computing in Python. *Nature Methods, 17*, 261–272.
> https://doi.org/10.1038/s41592-019-0586-2

Methods: "Ejective vs non-ejective contrasts were tested with two-tailed Welch (unequal-variance)
t-tests as implemented in SciPy (Virtanen et al., 2020). See the Limitations note on
pseudoreplication: these tests pool non-independent repetitions and two speakers, so the p-values
are descriptive of this sample, not inferential about Lakota or revitalization speakers generally."

(Supporting stack, optional to cite: NumPy — Harris et al., 2020, *Nature* 585:357; pandas —
McKinney, 2010, *Proc. 9th Python in Science Conf.*; Matplotlib — Hunter, 2007, *CiSE* 9(3):90.)

## AI assistance

Per the supervising instructor's directive, the analysis scripts (Praat + Python) and the
testing/spot-check process were developed with the assistance of Anthropic's Claude (Claude Code).
The appendix includes the scripts and a description of the validation harness (the ~12%
independent hand-remeasurement agreement check). Human-placed measurement boundaries and all
linguistic interpretation remain the authors'.

> Anthropic. (2025). *Claude* (Claude Code) [Large language model]. https://www.anthropic.com/claude

Methods/Appendix: "Pipeline code was written with the assistance of Claude Code (Anthropic, 2025);
all acoustic boundaries were placed and verified by hand, and a ~12% random subset was
independently re-measured to validate the automated battery."
