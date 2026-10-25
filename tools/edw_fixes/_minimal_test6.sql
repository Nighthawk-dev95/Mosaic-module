CREATE VIEW edw_test.enterprise_analytics._zz_minimal_test6
WITH METRICS
LANGUAGE YAML
AS
$$
version: 1.1
source: edw_test.enterprise_analytics.tbl_exam_inventory
dimensions:
  - name: Modality
    expr: exam_Modality_Code
measures:
  - name: Exam Count
    expr: COUNT(*)
joins:
  - name: dim_drafting
    source: edw_prod.enterprise_analytics_ref.drafting_eligible_rpids_vw
  - name: dim_category
    source: edw_prod.enterprise_analytics.tbl_exam_category_lookup_xwalk
$$;
