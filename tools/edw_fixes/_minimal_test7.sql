CREATE VIEW edw_test.enterprise_analytics._zz_minimal_test7
WITH METRICS
LANGUAGE YAML
AS
$$
version: 1.1
source: edw_test.enterprise_analytics.tbl_exam_inventory
dimensions:
  - name: Modality
    expr: exam_Modality_Code
  - name: NPI
    expr: reading_provider_npi
measures:
  - name: Exam Count
    expr: COUNT(*)
$$;
