# eodms-sentinel2-firemapping
Sentinel 2 real time data - use case - fire mapping

## Scientific value of the Jupyter workflow

The Jupyter notebook in this repository adds scientific value by making fire-mapping analysis transparent, testable, and reproducible.

1. Reproducible geospatial science
- The full processing chain (input geometry, scene selection, index generation, and visualization) is documented cell-by-cell.
- This makes it easier to rerun analyses for new fire events and compare results consistently across dates and locations.

2. Quantitative burn assessment support
- The workflow demonstrates fire-relevant spectral products such as NBR and BAI2 from Sentinel-2.
- These products support scientifically grounded interpretation of burn severity patterns rather than visual-only inspection.

3. Better quality control and uncertainty checks
- Intermediate outputs can be inspected directly, improving detection of cloud effects, scene mismatch, and AOI issues.
- This helps reduce false interpretation and increases confidence in downstream fire products.

4. Faster method development and validation
- Researchers can quickly test alternate indices, thresholds, date windows, and AOIs in one interactive environment.
- The notebook format accelerates hypothesis testing before operationalizing methods in automated scripts.

5. Stronger knowledge transfer
- The notebook captures both the method and rationale, supporting peer review, onboarding, and handoff to operations teams.

## Where to start

- Notebook: [examples/Sentinel2_Jun2025_FlinFlonDenareBeach_FireDemo.ipynb](examples/Sentinel2_Jun2025_FlinFlonDenareBeach_FireDemo.ipynb)
- Notebook details: [examples/README.md](examples/README.md)
