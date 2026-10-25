CREATE VIEW edw_test.enterprise_analytics._zz_minimal_test2
WITH METRICS
LANGUAGE YAML
AS
$$
version: 1.1

source: edw_test.enterprise_analytics.tbl_exam_inventory

joins:
  - name: dim_drafting
    source: edw_prod.enterprise_analytics_ref.drafting_eligible_rpids_vw
    'on': source.RPID_Procedure_Code = dim_drafting.rpid_procedure_code

dimensions:
  - name: Modality
    expr: exam_Modality_Code

measures:
  - name: Exam Count
    expr: COUNT(*)
$$;
