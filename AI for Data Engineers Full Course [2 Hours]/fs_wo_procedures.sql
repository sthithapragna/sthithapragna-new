/* =====================================================================
   Meridian FS -> Field Service Data Warehouse
   Work Order / Parts Usage subject area
   Target platform: Amazon Redshift (provisioned)

   These procedures are called nightly by the fs_wo_daily job chain.
   See MERIDIAN_FS_Mapping_Document_v1.0.xlsx for the field mapping.
   ===================================================================== */


create procedure fs_dw.usp_load_dim_work_order_fs(job_run_key integer)
    language plpgsql
as
$$
DECLARE
	sp_name					varchar :=		'';
	log_timestamp			timestamp := CONVERT_TIMEZONE('CST6CDT', SYSDATE);
	max_corrective_wo_key	bigint := 0;
	max_preventive_wo_key	bigint := 40000000;
	max_project_wo_key		bigint := 70000000;
	rec_count INT;
	tot_rec INT;
	v_SourceSystemKey INT;
	execution_timestamp		timestamp := CONVERT_TIMEZONE('CST6CDT', SYSDATE);
BEGIN

	sp_name := 'fs_dw.usp_load_dim_work_order_fs';
	RAISE INFO '%: Stored Procedure % starts Execution', log_timestamp, sp_name;

	/* Drop any temporary tables if they exist from a previous failure */
	DROP TABLE IF EXISTS #tmp_wo_inc;

	SELECT source_system_key into v_SourceSystemKey FROM common_ods.lkp_source_system WHERE source_system_name = 'MERIDIAN_FS';

	/* extract the max work_order_key from dim_work_order_fs */
	--SELECT NVL(MAX(work_order_key),max_corrective_wo_key) into max_corrective_wo_key FROM fs_dw.dim_work_order_fs WHERE work_order_key < 40000000;
	--SELECT NVL(MAX(work_order_key),max_preventive_wo_key) into max_preventive_wo_key FROM fs_dw.dim_work_order_fs WHERE work_order_key BETWEEN 40000000 AND 70000000;
	--SELECT NVL(MAX(work_order_key),max_project_wo_key) into max_project_wo_key FROM fs_dw.dim_work_order_fs WHERE work_order_key > 70000000;

	CREATE TABLE #tmp_wo_inc AS
		(
			SELECT
				max_corrective_wo_key + ROW_NUMBER() OVER (order by 1)					AS work_order_key,
				source_system_key,
				site_key,
				technician_key,
				work_order_number,
				work_order_type,
				work_order_type_description,
				wo_ref_id,
				source_system_site_code,
				source_system_technician_id,
				work_order_status,
				created_date,
				closed_date,
				priority_code,
				isdeleted_record,
				execution_timestamp AS record_insert_datetime,
				execution_timestamp AS record_update_datetime,
				job_run_id,
				site_hash_key,
				technician_hash_key,
				work_order_hash_key,
				delete_hash_key
			FROM (SELECT DISTINCT
				v_SourceSystemKey									AS source_system_key,
				-2													AS site_key,
				-2													AS technician_key,
				UPPER(wauf.wonum)									AS work_order_number,
				NVL(UPPER(wauf.wotyp),'')							AS work_order_type,
				NVL(t401.wotyptx,'')								AS work_order_type_description,
				NVL(UPPER(wauf.assetid),'')							AS wo_ref_id,
				NVL(UPPER(wauf.site),'')							AS source_system_site_code,
				NVL(UPPER(wauf.techid),'')							AS source_system_technician_id,
				CASE WHEN wstt.objid IS NOT NULL THEN 'closed' ELSE 'open' END	AS work_order_status,
				wauf.crdat											AS created_date,
				wauf.cldat											AS closed_date,
				NVL(wauf.prio,'')									AS priority_code,
				'N'													AS isdeleted_record,
				job_run_key											AS job_run_id,
				common_dw.f_fnv_hash(v_SourceSystemKey || NVL(UPPER(wauf.site),''))						AS site_hash_key,
				common_dw.f_fnv_hash(v_SourceSystemKey || NVL(UPPER(wauf.techid),''))					AS technician_hash_key,
				common_dw.f_fnv_hash(v_SourceSystemKey || UPPER(wauf.wonum))							AS work_order_hash_key,
				common_dw.f_fnv_hash(v_SourceSystemKey || UPPER(wauf.wonum) || UPPER(wauf.site) || UPPER(wauf.wotyp))	AS delete_hash_key
			FROM fsrc_vw.fs_wo_hdr_wauf_vw wauf --fedl_vw.meridian_wauf wauf
			LEFT OUTER JOIN fsrc_vw.fs_cfg_wotyp_t401_vw t401 --fedl_vw.meridian_t401 t401
				ON t401.wotyp = wauf.wotyp AND t401.lang = 'E' AND NVL(t401.chgtype,'') <> 'D'
			LEFT OUTER JOIN fsrc_vw.fs_wo_stat_wstt_vw wstt --fedl_vw.meridian_wstt wstt
				ON wstt.objid = wauf.wonum AND wstt.statcd IN ('S0040','S0055') AND NVL(UPPER(wstt.inactv),'') <> 'X' AND NVL(wstt.chgtype,'') <> 'D'
			WHERE
				--wauf.fsedl_ts >= incremental_range_start_time AND wauf.fsedl_ts < incremental_range_end_time AND
				wauf.wotyp IN ('C1','C2','C3') AND NVL(wauf.site,'') != '' AND NVL(wauf.chgtype,'') <> 'D')

			UNION ALL

			SELECT
				max_preventive_wo_key + ROW_NUMBER() OVER ()							AS work_order_key,
				source_system_key,
				site_key,
				technician_key,
				work_order_number,
				work_order_type,
				work_order_type_description,
				wo_ref_id,
				source_system_site_code,
				source_system_technician_id,
				work_order_status,
				created_date,
				closed_date,
				priority_code,
				isdeleted_record,
				execution_timestamp AS record_insert_datetime,
				execution_timestamp AS record_update_datetime,
				job_run_id,
				site_hash_key,
				technician_hash_key,
				work_order_hash_key,
				delete_hash_key
			FROM (SELECT DISTINCT
				v_SourceSystemKey									AS source_system_key,
				-2													AS site_key,
				-2													AS technician_key,
				UPPER(wauf.wonum)									AS work_order_number,
				NVL(UPPER(wauf.wotyp),'')							AS work_order_type,
				NVL(t401.wotyptx,'')								AS work_order_type_description,
				NVL(UPPER(wauf.assetid),'')							AS wo_ref_id,
				NVL(UPPER(wauf.site),'')							AS source_system_site_code,
				NVL(UPPER(wauf.techid),'')							AS source_system_technician_id,
				CASE WHEN wstt.objid IS NOT NULL THEN 'closed' ELSE 'open' END	AS work_order_status,
				wauf.crdat											AS created_date,
				wauf.cldat											AS closed_date,
				NVL(wauf.prio,'')									AS priority_code,
				'N'													AS isdeleted_record,
				job_run_key											AS job_run_id,
				common_dw.f_fnv_hash(v_SourceSystemKey || NVL(UPPER(wauf.site),''))						AS site_hash_key,
				common_dw.f_fnv_hash(v_SourceSystemKey || NVL(UPPER(wauf.techid),''))					AS technician_hash_key,
				common_dw.f_fnv_hash(v_SourceSystemKey || UPPER(wauf.wonum))							AS work_order_hash_key,
				common_dw.f_fnv_hash(v_SourceSystemKey || UPPER(wauf.wonum) || UPPER(wauf.site) || UPPER(wauf.wotyp))	AS delete_hash_key
			FROM fsrc_vw.fs_wo_hdr_wauf_vw wauf --fedl_vw.meridian_wauf wauf
			LEFT OUTER JOIN fsrc_vw.fs_cfg_wotyp_t401_vw t401 --fedl_vw.meridian_t401 t401
				ON t401.wotyp = wauf.wotyp AND t401.lang = 'E' AND NVL(t401.chgtype,'') <> 'D'
			LEFT OUTER JOIN fsrc_vw.fs_wo_stat_wstt_vw wstt --fedl_vw.meridian_wstt wstt
				ON wstt.objid = wauf.wonum AND wstt.statcd IN ('S0040','S0055') AND NVL(UPPER(wstt.inactv),'') <> 'X' AND NVL(wstt.chgtype,'') <> 'D'
			WHERE wauf.wotyp IN ('P1','P2') AND NVL(wauf.site,'') != '' AND NVL(wauf.chgtype,'') <> 'D')

			UNION ALL

			SELECT
				max_project_wo_key + ROW_NUMBER() OVER ()								AS work_order_key,
				source_system_key,
				site_key,
				technician_key,
				work_order_number,
				work_order_type,
				work_order_type_description,
				wo_ref_id,
				source_system_site_code,
				source_system_technician_id,
				work_order_status,
				created_date,
				closed_date,
				priority_code,
				isdeleted_record,
				execution_timestamp AS record_insert_datetime,
				execution_timestamp AS record_update_datetime,
				job_run_id,
				site_hash_key,
				technician_hash_key,
				work_order_hash_key,
				delete_hash_key
			FROM (SELECT DISTINCT
				v_SourceSystemKey									AS source_system_key,
				-2													AS site_key,
				-2													AS technician_key,
				UPPER(wauf.wonum)									AS work_order_number,
				NVL(UPPER(wauf.wotyp),'')							AS work_order_type,
				NVL(t401.wotyptx,'')								AS work_order_type_description,
				NVL(UPPER(wauf.contrid),'')							AS wo_ref_id,
				NVL(UPPER(wauf.site),'')							AS source_system_site_code,
				NVL(UPPER(wauf.techid),'')							AS source_system_technician_id,
				CASE WHEN wstt.objid IS NOT NULL THEN 'closed' ELSE 'open' END	AS work_order_status,
				wauf.crdat											AS created_date,
				wauf.cldat											AS closed_date,
				NVL(wauf.prio,'')									AS priority_code,
				'N'													AS isdeleted_record,
				job_run_key											AS job_run_id,
				common_dw.f_fnv_hash(v_SourceSystemKey || NVL(UPPER(wauf.site),''))						AS site_hash_key,
				common_dw.f_fnv_hash(v_SourceSystemKey || NVL(UPPER(wauf.techid),''))					AS technician_hash_key,
				common_dw.f_fnv_hash(v_SourceSystemKey || UPPER(wauf.wonum))							AS work_order_hash_key,
				common_dw.f_fnv_hash(v_SourceSystemKey || UPPER(wauf.wonum) || UPPER(wauf.site) || UPPER(wauf.wotyp))	AS delete_hash_key
			FROM fsrc_vw.fs_wo_hdr_wauf_vw wauf --fedl_vw.meridian_wauf wauf
			LEFT OUTER JOIN fsrc_vw.fs_cfg_wotyp_t401_vw t401 --fedl_vw.meridian_t401 t401
				ON t401.wotyp = wauf.wotyp AND t401.lang = 'E' AND NVL(t401.chgtype,'') <> 'D'
			LEFT OUTER JOIN fsrc_vw.fs_wo_stat_wstt_vw wstt --fedl_vw.meridian_wstt wstt
				ON wstt.objid = wauf.wonum AND wstt.statcd IN ('S0040','S0055') AND NVL(UPPER(wstt.inactv),'') <> 'X' AND NVL(wstt.chgtype,'') <> 'D'
			WHERE wauf.wotyp IN ('J1','J2') AND NVL(wauf.site,'') != '' AND NVL(wauf.chgtype,'') <> 'D')
		);

	SELECT count(*) INTO tot_rec FROM #tmp_wo_inc;
	RAISE INFO '%:%: Dataset is prepared: %', sp_name, log_timestamp, tot_rec;

	TRUNCATE TABLE fs_dw.dim_work_order_fs;

	INSERT INTO fs_dw.dim_work_order_fs
	SELECT work_order_key,
		   source_system_key,
		   site_key,
		   technician_key,
		   work_order_number,
		   work_order_type,
		   work_order_type_description,
		   wo_ref_id,
		   source_system_site_code,
		   source_system_technician_id,
		   work_order_status,
		   created_date,
		   closed_date,
		   priority_code,
		   isdeleted_record,
		   record_insert_datetime,
		   record_update_datetime,
		   job_run_id,
		   site_hash_key,
		   technician_hash_key,
		   work_order_hash_key,
		   delete_hash_key
	FROM #tmp_wo_inc;

	GET DIAGNOSTICS rec_count := ROW_COUNT;
	RAISE INFO '%:%: INSERTED Dataset into dim_work_order_fs: %', sp_name, log_timestamp, rec_count;

	UPDATE fs_dw.dim_work_order_fs SET site_key = site.site_key FROM common_dw.dim_site_flat site WHERE UPPER(site.source_system_name) || UPPER(site.site_code) = 'MERIDIAN' || source_system_site_code and NVL(source_system_site_code,'') <> '';
	UPDATE fs_dw.dim_work_order_fs SET technician_key = tech.technician_key FROM fs_dw.dim_technician_fs tech WHERE tech.technician_hash_key = dim_work_order_fs.technician_hash_key;

	RAISE INFO '%:%: UPDATED site_key, technician_key to latest in dim_work_order_fs', sp_name, log_timestamp;

/*
	UPDATE fs_dw.dim_work_order_fs SET isdeleted_record = 'Y'
	FROM (SELECT wonum, site, wotyp, fsedl_ts FROM fedl_deletes.meridian_wauf WHERE fsedl_ts >= incremental_range_start_time AND fsedl_ts < incremental_range_end_time AND odq_changemode = 'D') edl
	WHERE common_dw.f_fnv_hash(v_SourceSystemKey || UPPER(edl.wonum) || UPPER(edl.site) || UPPER(edl.wotyp)) = dim_work_order_fs.delete_hash_key
	;
*/

	RAISE INFO '%:%: Stored Procedure - FINISHED', sp_name, log_timestamp;

	EXCEPTION
	WHEN OTHERS THEN
		   RAISE EXCEPTION 'Error : %',
	SQLERRM ;

	DROP TABLE IF EXISTS #tmp_wo_inc;
END;
$$;


create procedure fs_dw.usp_load_dim_technician_fs(job_run_key integer)
    language plpgsql
as
$$
DECLARE
	sp_name					varchar :=		'';
	log_timestamp			timestamp DEFAULT GETDATE();
	max_technician_key		bigint := 0;
	rec_count INT;
	tot_rec INT;
	v_SourceSystemKey INT;
	execution_timestamp		timestamp := CONVERT_TIMEZONE('CST6CDT', SYSDATE);
BEGIN

	sp_name := 'fs_dw.usp_load_dim_technician_fs';
	RAISE INFO '%: Stored Procedure % starts Execution', log_timestamp, sp_name;

	DROP TABLE IF EXISTS #tmp_tech_inc;

	SELECT source_system_key into v_SourceSystemKey FROM common_ods.lkp_source_system WHERE source_system_name = 'MERIDIAN_FS';

	CREATE TABLE #tmp_tech_inc AS
		(
			SELECT
				max_technician_key + ROW_NUMBER() OVER (order by 1)						AS technician_key,
				source_system_key,
				site_key,
				technician_id,
				technician_name,
				source_system_site_code,
				crew_code,
				hire_date,
				technician_status,
				isdeleted_record,
				execution_timestamp AS record_insert_datetime,
				execution_timestamp AS record_update_datetime,
				job_run_id,
				site_hash_key,
				technician_hash_key
			FROM (
				SELECT DISTINCT
					v_SourceSystemKey								AS source_system_key,
					-2												AS site_key,
					UPPER(tech.techid)								AS technician_id,
					NVL(techt.techname,'')							AS technician_name,
					NVL(UPPER(tech.site),'')						AS source_system_site_code,
					NVL(UPPER(tech.crewcd),'')						AS crew_code,
					tech.hiredt										AS hire_date,
					CASE WHEN tech.termdt = '9999-12-31' THEN 'active' ELSE 'terminated' END	AS technician_status,
					'N'												AS isdeleted_record,
					job_run_key										AS job_run_id,
					common_dw.f_fnv_hash(v_SourceSystemKey || UPPER(tech.site))		AS site_hash_key,
					common_dw.f_fnv_hash(v_SourceSystemKey || UPPER(tech.techid))	AS technician_hash_key
				FROM fsrc_vw.fs_tech_mstr_tech_vw tech --fedl_vw.meridian_tech tech
				INNER JOIN fsrc_vw.fs_tech_txt_techt_vw techt --fedl_vw.meridian_techt techt
					ON techt.techid = tech.techid AND techt.lang = 'E' AND NVL(techt.chgtype,'') <> 'D'
				WHERE tech.termdt = '9999-12-31' AND NVL(tech.chgtype,'') <> 'D'
				)
		);

	SELECT count(*) INTO tot_rec FROM #tmp_tech_inc;
	RAISE INFO '%:%: Dataset is prepared: %', sp_name, log_timestamp, tot_rec;

	TRUNCATE TABLE fs_dw.dim_technician_fs;

	INSERT INTO fs_dw.dim_technician_fs
	SELECT technician_key,
		   source_system_key,
		   site_key,
		   technician_id,
		   technician_name,
		   source_system_site_code,
		   crew_code,
		   hire_date,
		   technician_status,
		   isdeleted_record,
		   record_insert_datetime,
		   record_update_datetime,
		   job_run_id,
		   site_hash_key,
		   technician_hash_key
	FROM #tmp_tech_inc;

	GET DIAGNOSTICS rec_count := ROW_COUNT;
	RAISE INFO '%:%: INSERTED Dataset into dim_technician_fs: %', sp_name, log_timestamp, rec_count;

	UPDATE fs_dw.dim_technician_fs SET site_key = site.site_key FROM common_dw.dim_site_flat site WHERE UPPER(site.source_system_name) || UPPER(site.site_code) = 'MERIDIAN' || source_system_site_code AND NVL(source_system_site_code,'') != '';

	RAISE INFO '%:%: UPDATED site_key to latest in dim_technician_fs', sp_name, log_timestamp;
	RAISE INFO '%:%: Stored Procedure - FINISHED', sp_name, log_timestamp;

	EXCEPTION
	WHEN OTHERS THEN
		   RAISE EXCEPTION 'Error : %',
	SQLERRM ;

	DROP TABLE IF EXISTS #tmp_tech_inc;
END;
$$;


create procedure fs_dw.usp_load_dim_asset_fs(job_run_key integer)
    language plpgsql
as
$$
DECLARE
	sp_name					varchar :=		'';
	log_timestamp			timestamp := CONVERT_TIMEZONE('CST6CDT', SYSDATE);
	max_asset_key			bigint := 0;
	rec_count INT;
	tot_rec INT;
	v_SourceSystemKey INT;
	execution_timestamp		timestamp := CONVERT_TIMEZONE('CST6CDT', SYSDATE);
BEGIN

	sp_name := 'fs_dw.usp_load_dim_asset_fs';
	RAISE INFO '%: Stored Procedure % starts Execution', log_timestamp, sp_name;

	DROP TABLE IF EXISTS #tmp_asset_inc;

	SELECT source_system_key into v_SourceSystemKey FROM common_ods.lkp_source_system WHERE source_system_name = 'MERIDIAN_FS';

	CREATE TABLE #tmp_asset_inc AS
		(
			SELECT
				max_asset_key + ROW_NUMBER() OVER (order by 1)							AS asset_key,
				source_system_key,
				site_key,
				asset_number,
				asset_description,
				source_system_site_code,
				asset_type,
				asset_status,
				install_date,
				isdeleted_record,
				execution_timestamp AS record_insert_datetime,
				execution_timestamp AS record_update_datetime,
				job_run_id,
				site_hash_key,
				asset_hash_key
			FROM (
				SELECT DISTINCT
					v_SourceSystemKey								AS source_system_key,
					-2												AS site_key,
					UPPER(assm.assetid)								AS asset_number,
					NVL(asst.assetdesc,'')							AS asset_description,
					NVL(UPPER(assm.site),'')						AS source_system_site_code,
					NVL(UPPER(assm.asstyp),'')						AS asset_type,
					CASE WHEN wstt.objid IS NOT NULL THEN 'inactive' ELSE 'active' END	AS asset_status,
					assm.instdt										AS install_date,
					'N'												AS isdeleted_record,
					job_run_key										AS job_run_id,
					common_dw.f_fnv_hash(v_SourceSystemKey || NVL(UPPER(assm.site),''))		AS site_hash_key,
					common_dw.f_fnv_hash(v_SourceSystemKey || UPPER(assm.assetid))			AS asset_hash_key
				FROM fsrc_vw.fs_asset_mstr_assm_vw assm --fedl_vw.meridian_assm assm
				LEFT OUTER JOIN fsrc_vw.fs_asset_txt_asst_vw asst --fedl_vw.meridian_asst asst
					ON UPPER(asst.assetid) = UPPER(assm.assetid) AND asst.lang = 'E' AND NVL(asst.chgtype,'') <> 'D'
				LEFT OUTER JOIN fsrc_vw.fs_wo_stat_wstt_vw wstt --fedl_vw.meridian_wstt wstt
					ON wstt.objid = assm.assetid AND wstt.statcd IN ('S0040','S0055') AND NVL(UPPER(wstt.inactv),'') <> 'X' AND NVL(wstt.chgtype,'') <> 'D'
				WHERE NVL(assm.chgtype,'') <> 'D'
				)
		);

	SELECT count(*) INTO tot_rec FROM #tmp_asset_inc;
	RAISE INFO '%:%: Dataset is prepared: %', sp_name, log_timestamp, tot_rec;

	TRUNCATE TABLE fs_dw.dim_asset_fs;

	INSERT INTO fs_dw.dim_asset_fs
	SELECT asset_key,
		   source_system_key,
		   site_key,
		   asset_number,
		   asset_description,
		   source_system_site_code,
		   asset_type,
		   asset_status,
		   install_date,
		   isdeleted_record,
		   record_insert_datetime,
		   record_update_datetime,
		   job_run_id,
		   site_hash_key,
		   asset_hash_key
	FROM #tmp_asset_inc;

	GET DIAGNOSTICS rec_count := ROW_COUNT;
	RAISE INFO '%:%: INSERTED Dataset into dim_asset_fs: %', sp_name, log_timestamp, rec_count;

	UPDATE fs_dw.dim_asset_fs SET site_key = site.site_key FROM common_dw.dim_site_flat site WHERE UPPER(site.source_system_name) || UPPER(site.site_code) = 'MERIDIAN' || source_system_site_code and NVL(source_system_site_code,'') <> '';

	RAISE INFO '%:%: Stored Procedure - FINISHED', sp_name, log_timestamp;

	EXCEPTION
	WHEN OTHERS THEN
		   RAISE EXCEPTION 'Error : %',
	SQLERRM ;

	DROP TABLE IF EXISTS #tmp_asset_inc;
END;
$$;


create procedure fs_dw.usp_load_dim_wo_asset_fs(job_run_key integer)
    language plpgsql
as
$$
DECLARE
	sp_name					varchar :=		'';
	log_timestamp			timestamp := CONVERT_TIMEZONE('CST6CDT', SYSDATE);
	max_wo_asset_key		bigint := 0;
	rec_count INT;
	tot_rec INT;
	v_SourceSystemKey INT;
	execution_timestamp		timestamp := CONVERT_TIMEZONE('CST6CDT', SYSDATE);
BEGIN

	sp_name := 'fs_dw.usp_load_dim_wo_asset_fs';
	RAISE INFO '%: Stored Procedure % starts Execution', log_timestamp, sp_name;

	DROP TABLE IF EXISTS #tmp_wo_asset;

	TRUNCATE TABLE fs_dw.dim_wo_asset_fs;

	CREATE TABLE #tmp_wo_asset AS
		(
			SELECT
				max_wo_asset_key + ROW_NUMBER() OVER (order by 1)						AS wo_asset_key,
				source_system_key,
				site_key,
				technician_key,
				work_order_key,
				asset_key,
				work_order_number,
				asset_number,
				source_system_site_code,
				isdeleted_record,
				execution_timestamp AS record_insert_datetime,
				execution_timestamp AS record_update_datetime,
				job_run_id
			FROM
			(SELECT DISTINCT
				wo.source_system_key,
				wo.site_key,
				wo.technician_key,
				wo.work_order_key,
				ast.asset_key,
				wo.work_order_number,
				ast.asset_number,
				wo.source_system_site_code,
				'N'												AS isdeleted_record,
				job_run_key										AS job_run_id
			FROM fs_dw.dim_work_order_fs wo
			INNER JOIN fs_dw.dim_asset_fs ast
				ON ast.asset_number = wo.wo_ref_id AND
				   ast.isdeleted_record = 'N'
			WHERE wo.isdeleted_record = 'N'
			)
		);

	SELECT count(*) INTO tot_rec FROM #tmp_wo_asset;
	RAISE INFO '%:%: full Dataset is prepared: %', sp_name, log_timestamp, tot_rec;

	TRUNCATE TABLE fs_dw.dim_wo_asset_fs;

	INSERT INTO fs_dw.dim_wo_asset_fs
	SELECT wo_asset_key,
		   source_system_key,
		   site_key,
		   technician_key,
		   work_order_key,
		   asset_key,
		   work_order_number,
		   asset_number,
		   source_system_site_code,
		   isdeleted_record,
		   record_insert_datetime,
		   record_update_datetime,
		   job_run_id
	FROM #tmp_wo_asset;

	GET DIAGNOSTICS rec_count := ROW_COUNT;
	RAISE INFO '%:%: INSERTED full dataset into dim_wo_asset_fs: %', sp_name, log_timestamp, rec_count;

	RAISE INFO '%:%: Stored Procedure - FINISHED', sp_name, log_timestamp;

	EXCEPTION
	WHEN OTHERS THEN
		   RAISE EXCEPTION 'Error : %',
	SQLERRM ;

	DROP TABLE IF EXISTS #tmp_wo_asset;
END;
$$;


create procedure fs_dw.usp_load_dim_part_site_fs(job_run_key integer)
    language plpgsql
as
$$
DECLARE
	sp_name					varchar :=		'';
	log_timestamp			timestamp := CONVERT_TIMEZONE('CST6CDT', SYSDATE);
	max_part_site_key		bigint;
	rec_count INT;
	tot_rec INT;
	v_SourceSystemKey INT;
	execution_timestamp		timestamp := CONVERT_TIMEZONE('CST6CDT', SYSDATE);
BEGIN

	sp_name := 'fs_dw.usp_load_dim_part_site_fs';
	RAISE INFO '%: Stored Procedure % starts Execution', log_timestamp, sp_name;

	TRUNCATE TABLE fs_dw.dim_part_site_fs;

	DROP TABLE IF EXISTS #tmp_part_site_inc;

	SELECT source_system_key into v_SourceSystemKey FROM common_ods.lkp_source_system WHERE source_system_name = 'MERIDIAN_FS';

	/* extract the max part_site_key from dim_part_site_fs table*/
	SELECT NVL(MAX(part_site_key),0) into max_part_site_key FROM fs_dw.dim_part_site_fs;

	CREATE TABLE #tmp_part_site_inc AS
		(
			SELECT
				max_part_site_key + ROW_NUMBER() OVER (order by 1)						AS part_site_key,
				source_system_key,
				part_key,
				site_key,
				source_system_part_number,
				source_system_site_code,
				stock_location,
				part_type,
				unit_of_measure,
				planning_type,
				minimum_stock_level,
				maximum_stock_level,
				is_planned_part,
				isdeleted_record,
				execution_timestamp AS record_insert_datetime,
				execution_timestamp AS record_update_datetime,
				job_run_id,
				part_hash_key,
				site_hash_key,
				part_site_hash_key,
				delete_hash_key
			FROM (SELECT DISTINCT
					v_SourceSystemKey								AS source_system_key,
					-2												AS part_key,
					-2												AS site_key,
					UPPER(pmats.partno)								AS source_system_part_number,
					UPPER(pmats.site)								AS source_system_site_code,
					UPPER(TRIM(pmats.stloc) + '|' + TRIM(pmats.plntyp))	AS stock_location,
					NVL(UPPER(pmat.ptyp),'')						AS part_type,
					NVL(UPPER(pmat.uom),'')							AS unit_of_measure,
					NVL(UPPER(pmats.plntyp),'')						AS planning_type,
					pmats.minqty									AS minimum_stock_level,
					pmats.maxqty									AS maximum_stock_level,
					CASE WHEN NVL(pmats.plntyp,'') = 'R1' AND NVL(pmats.reordfl,'') = 'X' THEN 'Y' ELSE 'N' END	AS is_planned_part,
					'N'												AS isdeleted_record,
					job_run_key										AS job_run_id,
					common_dw.f_fnv_hash(v_SourceSystemKey || NVL(UPPER(pmats.partno),''))	AS part_hash_key,
					common_dw.f_fnv_hash(v_SourceSystemKey || NVL(UPPER(pmats.site),''))		AS site_hash_key,
					common_dw.f_fnv_hash(v_SourceSystemKey || NVL(UPPER(pmats.partno),'') || NVL(UPPER(pmats.site),''))	AS part_site_hash_key,
					common_dw.f_fnv_hash(v_SourceSystemKey || NVL(UPPER(pmats.partno),'') || NVL(UPPER(pmats.site),'') || NVL(UPPER(pmats.stloc),''))	AS delete_hash_key
			FROM fsrc_vw.fs_part_site_pmats_vw pmats --fedl_vw.meridian_pmats pmats
			INNER JOIN fsrc_vw.fs_part_mstr_pmat_vw pmat --fedl_vw.meridian_pmat pmat
				ON pmat.partno = pmats.partno AND NVL(pmat.chgtype,'') <> 'D'
			WHERE ((NVL(pmats.stloc,'') = '1000') OR (NVL(pmats.stloc,'') = '2000' AND NVL(pmat.ptyp,'') IN ('ZRPR','ZCON'))) AND NVL(pmats.chgtype,'') <> 'D'
				)
		);

	SELECT count(*) INTO tot_rec FROM #tmp_part_site_inc;
	RAISE INFO '%:%: Dataset is prepared: %', sp_name, log_timestamp, tot_rec;

	INSERT INTO fs_dw.dim_part_site_fs
	SELECT part_site_key,
		   source_system_key,
		   part_key,
		   site_key,
		   source_system_part_number,
		   source_system_site_code,
		   stock_location,
		   part_type,
		   unit_of_measure,
		   planning_type,
		   minimum_stock_level,
		   maximum_stock_level,
		   is_planned_part,
		   isdeleted_record,
		   record_insert_datetime,
		   record_update_datetime,
		   job_run_id,
		   part_hash_key,
		   site_hash_key,
		   part_site_hash_key,
		   delete_hash_key
	FROM #tmp_part_site_inc;

	GET DIAGNOSTICS rec_count := ROW_COUNT;
	RAISE INFO '%:%: INSERTED dataset into dim_part_site_fs: %', sp_name, log_timestamp, rec_count;

	UPDATE fs_dw.dim_part_site_fs SET part_key = part.part_key FROM fs_dw.dim_part_fs part WHERE part.part_hash_key = dim_part_site_fs.part_hash_key;
	UPDATE fs_dw.dim_part_site_fs SET site_key = site.site_key FROM common_dw.dim_site_flat site WHERE UPPER(site.source_system_name) || UPPER(site.site_code) = 'MERIDIAN' || source_system_site_code and NVL(source_system_site_code,'') <> '';

	RAISE INFO '%:%: UPDATED part_key, site_key to latest in dim_part_site_fs', sp_name, log_timestamp;
	RAISE INFO '%:%: Stored Procedure - FINISHED', sp_name, log_timestamp;

	EXCEPTION
	WHEN OTHERS THEN
		   RAISE EXCEPTION 'Error : %',
	SQLERRM ;

	DROP TABLE IF EXISTS #tmp_part_site_inc;
END;
$$;


create procedure fs_dw.usp_load_fct_wo_parts_usage_fs(job_run_key integer)
    language plpgsql
as
$$
DECLARE
	sp_name					varchar :=		'';
	log_timestamp			timestamp := CONVERT_TIMEZONE('CST6CDT', SYSDATE);
	max_wo_parts_usage_key	bigint := 0;
	tot_rec INT;
	v_SourceSystemKey INT;
	execution_timestamp		timestamp := CONVERT_TIMEZONE('CST6CDT', SYSDATE);
BEGIN

	sp_name := 'fs_dw.usp_load_fct_wo_parts_usage_fs';
	RAISE INFO '%: Stored Procedure % starts Execution', log_timestamp, sp_name;

	TRUNCATE TABLE fs_dw.fct_wo_parts_usage_fs;

	DROP TABLE IF EXISTS #wmov;

	SELECT source_system_key into v_SourceSystemKey FROM common_ods.lkp_source_system WHERE source_system_name = 'MERIDIAN_FS';

	SELECT NVL(MAX(fct_wo_parts_usage_key),max_wo_parts_usage_key) into max_wo_parts_usage_key FROM fs_dw.fct_wo_parts_usage_fs;

	CREATE TABLE #wmov AS
		(	SELECT pmats.partno, pmats.site, pmats.stloc, pmat.ptyp, mv.mvttyp, mv.qty, TO_DATE(mv.postdt,'YYYY.MM.DD') AS postdt
			FROM fsrc_vw.fs_part_site_pmats_vw pmats --fedl_vw.meridian_pmats pmats
			INNER JOIN fsrc_vw.fs_part_mstr_pmat_vw pmat --fedl_vw.meridian_pmat pmat
				ON pmats.partno = pmat.partno AND NVL(pmat.chgtype,'') <> 'D'
			LEFT JOIN fsrc_vw.fs_wo_mvt_wmov_vw mv --fedl_vw.meridian_wmov mv
				ON pmats.partno = mv.partno AND pmats.site = mv.site AND pmats.stloc = mv.stloc AND NVL(mv.chgtype,'') <> 'D'
			WHERE ((ISNULL(pmats.stloc,'') = '1000') OR (ISNULL(pmats.stloc,'') = '2000' AND ISNULL(pmat.ptyp,'') IN ('ZRPS','ZCON'))) AND NVL(pmats.chgtype,'') <> 'D'
		);

	INSERT INTO fs_dw.fct_wo_parts_usage_fs
	(
		fct_wo_parts_usage_key,
		source_system_key,
		part_key,
		site_key,
		part_site_key,
		source_system_part_number,
		source_system_site_code,
		total_consumed_12_months,
		total_consumed_24_months,
		total_consumed_60_months,
		isdeleted_record,
		record_insert_datetime,
		record_update_datetime,
		job_run_id,
		part_hash_key,
		site_hash_key,
		part_site_hash_key,

		parts_issued_12_months,
		parts_returned_12_months,

		parts_issued_24_months,
		parts_returned_24_months,

		parts_issued_60_months,
		parts_returned_60_months
	)
	WITH cte_12 AS
	(	SELECT	cte_12.partno, cte_12.site,
				SUM(CASE WHEN ISNULL(cte_12.mvttyp,'') IN ('261','262','291','301','311','321','601','641','961') THEN cte_12.qty ELSE 0 END) AS parts_issued_12_months,
				SUM(CASE WHEN ISNULL(cte_12.mvttyp,'') IN ('262','292','302','312','322','602','642') THEN cte_12.qty ELSE 0 END) AS parts_returned_12_months,

				SUM(CASE WHEN ISNULL(cte_12.mvttyp,'') IN ('261','262','291','301','311','321','601','641','961') THEN cte_12.qty ELSE 0 END)
			   -SUM(CASE WHEN ISNULL(cte_12.mvttyp,'') IN ('262','292','302','312','322','602','642') THEN cte_12.qty ELSE 0 END) AS consumed_12_months
		FROM #wmov cte_12
		WHERE cte_12.postdt BETWEEN TRUNC(dateadd(year, -1, CURRENT_DATE - 1)) AND (CURRENT_DATE - 1)
		AND ISNULL(cte_12.ptyp,'') NOT IN ('ZOBS','ZKIT')
		GROUP BY cte_12.partno, cte_12.site
	),
	cte_24 AS
	(	SELECT	cte_24.partno, cte_24.site,
				SUM(CASE WHEN ISNULL(cte_24.mvttyp,'') IN ('261','262','291','301','311','321','601','641','961') THEN cte_24.qty ELSE 0 END) AS parts_issued_24_months,
				SUM(CASE WHEN ISNULL(cte_24.mvttyp,'') IN ('262','292','302','312','322','602','642') THEN cte_24.qty ELSE 0 END) AS parts_returned_24_months,

				SUM(CASE WHEN ISNULL(cte_24.mvttyp,'') IN ('261','262','291','301','311','321','601','641','961') THEN cte_24.qty ELSE 0 END)
			   -SUM(CASE WHEN ISNULL(cte_24.mvttyp,'') IN ('262','292','302','312','322','602','642') THEN cte_24.qty ELSE 0 END) AS consumed_24_months
		FROM #wmov cte_24
		WHERE cte_24.postdt BETWEEN TRUNC(dateadd(year, -2, CURRENT_DATE - 1)) AND (CURRENT_DATE - 1)
		AND ISNULL(cte_24.ptyp,'') NOT IN ('ZOBS','ZKIT')
		GROUP BY cte_24.partno, cte_24.site
	),
	cte_60 AS
	(	SELECT	cte_60.partno, cte_60.site,
				SUM(CASE WHEN ISNULL(cte_60.mvttyp,'') IN ('261','262','291','301','311','321','601','641','961') THEN cte_60.qty ELSE 0 END) AS parts_issued_60_months,
				SUM(CASE WHEN ISNULL(cte_60.mvttyp,'') IN ('262','292','302','312','322','602','642') THEN cte_60.qty ELSE 0 END) AS parts_returned_60_months,

				SUM(CASE WHEN ISNULL(cte_60.mvttyp,'') IN ('261','262','291','301','311','321','601','641','961') THEN cte_60.qty ELSE 0 END)
			   -SUM(CASE WHEN ISNULL(cte_60.mvttyp,'') IN ('262','292','302','312','322','602','642') THEN cte_60.qty ELSE 0 END) AS consumed_60_months
		FROM #wmov cte_60
		WHERE cte_60.postdt BETWEEN TRUNC(dateadd(year, -5, CURRENT_DATE - 1)) AND (CURRENT_DATE - 1)
		AND ISNULL(cte_60.ptyp,'') NOT IN ('ZOBS','ZKIT')
		GROUP BY cte_60.partno, cte_60.site
	)
	SELECT
		max_wo_parts_usage_key + ROW_NUMBER() OVER (order by 1) AS fct_wo_parts_usage_key,
		v_SourceSystemKey AS source_system_key,
		-2	AS part_key,
		-2	AS site_key,
		-2	AS part_site_key,
		cte.partno AS source_system_part_number,
		cte.site AS source_system_site_code,

		ISNULL(cte_12.consumed_12_months,0) AS total_consumed_12_months,
		ISNULL(cte_24.consumed_24_months,0) AS total_consumed_24_months,
		ISNULL(cte_60.consumed_60_months,0) AS total_consumed_60_months,

		'N' AS isdeleted_record,
		execution_timestamp AS record_insert_datetime,
		execution_timestamp AS record_update_datetime,
		job_run_key AS job_run_id,
		common_dw.f_fnv_hash(v_SourceSystemKey || UPPER(cte.partno))						AS part_hash_key,
		common_dw.f_fnv_hash(v_SourceSystemKey || UPPER(cte.site))							AS site_hash_key,
		common_dw.f_fnv_hash(v_SourceSystemKey || UPPER(cte.partno) || UPPER(cte.site))		AS part_site_hash_key,

		ISNULL(cte_12.parts_issued_12_months,0) AS parts_issued_12_months,
		ISNULL(cte_12.parts_returned_12_months,0) AS parts_returned_12_months,

		ISNULL(cte_24.parts_issued_24_months,0) AS parts_issued_24_months,
		ISNULL(cte_24.parts_returned_24_months,0) AS parts_returned_24_months,

		ISNULL(cte_60.parts_issued_60_months,0) AS parts_issued_60_months,
		ISNULL(cte_60.parts_returned_60_months,0) AS parts_returned_60_months

	FROM (SELECT DISTINCT partno, site from #wmov) cte
	LEFT JOIN cte_12 ON cte.partno = cte_12.partno AND cte.site = cte_12.site
	LEFT JOIN cte_24 ON cte.partno = cte_24.partno AND cte.site = cte_24.site
	LEFT JOIN cte_60 ON cte.partno = cte_60.partno AND cte.site = cte_60.site;

	SELECT count(*) INTO tot_rec FROM fs_dw.fct_wo_parts_usage_fs;
	RAISE INFO '%:%: INSERTED dataset into fs_dw.fct_wo_parts_usage_fs: %', sp_name, log_timestamp, tot_rec;

	UPDATE fs_dw.fct_wo_parts_usage_fs SET part_key = part.part_key FROM fs_dw.dim_part_fs part WHERE part.part_hash_key = fct_wo_parts_usage_fs.part_hash_key;
	UPDATE fs_dw.fct_wo_parts_usage_fs SET site_key = site.site_key FROM common_dw.dim_site_flat site WHERE UPPER(site.source_system_name) || UPPER(site.site_code) = 'MERIDIAN' || source_system_site_code and source_system_site_code <> '';
	UPDATE fs_dw.fct_wo_parts_usage_fs SET part_site_key = ps.part_site_key FROM fs_dw.dim_part_site_fs ps WHERE ps.part_site_hash_key = fct_wo_parts_usage_fs.part_site_hash_key;

	RAISE INFO '%:%: UPDATED part_key, site_key, part_site_key to latest in fct_wo_parts_usage_fs', sp_name, log_timestamp;
	RAISE INFO '%:%: Stored Procedure - FINISHED', sp_name, log_timestamp;

	EXCEPTION
	WHEN OTHERS THEN
		   RAISE EXCEPTION 'Error : %',
	SQLERRM ;

	DROP TABLE IF EXISTS #wmov;
END;
$$;


create procedure fs_dw.usp_load_fct_wo_backlog_fs(job_run_key integer)
    language plpgsql
as
$$
DECLARE
	sp_name					varchar :=		'';
	log_timestamp			timestamp := CONVERT_TIMEZONE('CST6CDT', SYSDATE);
	max_backlog_key			bigint := 0;
	rec_count INT;
	tot_rec INT;
	v_SourceSystemKey INT;
	execution_timestamp		timestamp := CONVERT_TIMEZONE('CST6CDT', SYSDATE);
BEGIN

	sp_name := 'fs_dw.usp_load_fct_wo_backlog_fs';
	RAISE INFO '%: Stored Procedure % starts Execution', log_timestamp, sp_name;

	DROP TABLE IF EXISTS #tmp_backlog_inc;

	SELECT source_system_key into v_SourceSystemKey FROM common_ods.lkp_source_system WHERE source_system_name = 'MERIDIAN_FS';

	CREATE TABLE #tmp_backlog_inc AS
		(
			WITH res AS
				(
					SELECT
						part_site_hash_key,
						stock_location,
						SUM(reserved_val) AS reserved_val_num,
						CASE WHEN SUM(reserved_qty) > 0.0 THEN SUM(reserved_qty) ELSE 0.0 END AS reserved_qty_denom
					FROM (
							SELECT
								part_site_hash_key,
								unit_cost * reserved_qty AS reserved_val,
								reserved_qty,
								stock_location
							FROM fs_dw.fct_wo_reservation_fs
							WHERE planning_type NOT IN ('X0','X9')
						 )
					GROUP BY part_site_hash_key, stock_location
				),
				opn AS
				(
					SELECT
						UPPER(detail.source_system_part_number)	AS source_system_part_number,
						UPPER(detail.source_system_site_code)	AS source_system_site_code,
						UPPER(detail.stock_location)			AS stock_location,
						SUM(quantity_outstanding)				AS sum_qty_outstanding
					FROM fs_dw.fct_wo_detail_fs detail
					WHERE UPPER(operation_status) = 'RELEASED'
					AND	  NVL(reservation_delete_indicator,'') <> 'X'
					GROUP BY UPPER(detail.source_system_part_number), UPPER(detail.source_system_site_code), UPPER(detail.stock_location)
				)

			SELECT
				max_backlog_key + ROW_NUMBER() OVER (order by 1)						AS fct_wo_backlog_key,
				source_system_key,
				part_key,
				site_key,
				part_site_key,
				source_system_part_number,
				source_system_site_code,
				shortfall_quantity,
				shortfall_value,
				quantity_outstanding,
				committed_shortfall_quantity,
				committed_shortfall_value,
				uncommitted_shortfall_quantity,
				uncommitted_shortfall_value,
				isdeleted_record,
				execution_timestamp AS record_insert_datetime,
				execution_timestamp AS record_update_datetime,
				job_run_id,
				part_hash_key,
				site_hash_key,
				part_site_hash_key,
				delete_hash_key,
				stock_location
			FROM (
					SELECT DISTINCT
						v_SourceSystemKey													AS source_system_key,
						-2																	AS part_key,
						-2																	AS site_key,
						-2																	AS part_site_key,
						UPPER(pmats.partno)													AS source_system_part_number,
						UPPER(pmats.site)													AS source_system_site_code,
						(CASE WHEN NVL(reserved_qty_denom,0.0) > 0.0 THEN reserved_val_num/reserved_qty_denom
							  ELSE 0.0
						 END)																AS unit_cost_part_site,
						CASE WHEN is_planned_part = 'Y' THEN
									CASE WHEN (NVL(stock.maximum_stock_level,0.0) - NVL(reserved_qty_denom,0.0)) < 0.0 THEN 0.0
										 ELSE (NVL(stock.maximum_stock_level,0.0) - NVL(reserved_qty_denom,0.0))
									END
							 ELSE NVL(reserved_qty_denom,0.0)
						END																	AS shortfall_quantity,
						shortfall_quantity * unit_cost_part_site							AS shortfall_value,
						NVL(opn.sum_qty_outstanding,0.0)									AS quantity_outstanding,
						CASE WHEN shortfall_quantity = 0.0 THEN 0.0
							 WHEN quantity_outstanding >= shortfall_quantity THEN shortfall_quantity
							 WHEN shortfall_quantity > quantity_outstanding THEN quantity_outstanding
						END																	AS committed_shortfall_quantity,
						committed_shortfall_quantity * unit_cost_part_site					AS committed_shortfall_value,
						CASE WHEN shortfall_quantity = 0.0 OR committed_shortfall_quantity = shortfall_quantity THEN 0.0
							 ELSE shortfall_quantity - committed_shortfall_quantity
						END																	AS uncommitted_shortfall_quantity,
						uncommitted_shortfall_quantity * unit_cost_part_site				AS uncommitted_shortfall_value,
						'N'																	AS isdeleted_record,
						job_run_key															AS job_run_id,
						common_dw.f_fnv_hash(v_SourceSystemKey || UPPER(pmats.partno))						AS part_hash_key,
						common_dw.f_fnv_hash(v_SourceSystemKey || UPPER(pmats.site))						AS site_hash_key,
						common_dw.f_fnv_hash(v_SourceSystemKey || UPPER(pmats.partno) || UPPER(pmats.site))	AS part_site_hash_key,
						common_dw.f_fnv_hash(v_SourceSystemKey || UPPER(pmats.partno) || UPPER(pmats.site) || NVL(UPPER(pmats.stloc)),'')	AS delete_hash_key,
						res.stock_location													AS stock_location
					FROM fsrc_vw.fs_part_site_pmats_vw pmats
					INNER JOIN fsrc_vw.fs_part_mstr_pmat_vw pmat ON pmat.partno = pmats.partno AND NVL(pmat.chgtype,'') <> 'D'
					INNER JOIN fs_dw.dim_part_site_fs stock ON stock.part_site_hash_key = common_dw.f_fnv_hash(v_SourceSystemKey || UPPER(pmats.partno) || UPPER(pmats.site))
					LEFT OUTER JOIN res ON res.part_site_hash_key = common_dw.f_fnv_hash(v_SourceSystemKey || UPPER(pmats.partno) || UPPER(pmats.site))
					LEFT OUTER JOIN opn ON UPPER(opn.source_system_part_number) = UPPER(pmats.partno) AND UPPER(opn.source_system_site_code) = UPPER(pmats.site) AND UPPER(opn.stock_location) = UPPER(res.stock_location)
					WHERE NVL(pmats.stloc,'') = '1000' OR (NVL(pmats.stloc,'') = '2000' AND NVL(pmat.ptyp,'') IN ('ZRPR','ZCON')) AND NVL(pmats.chgtype,'') <> 'D'
				)
		);

	SELECT count(*) INTO tot_rec FROM #tmp_backlog_inc;
	RAISE INFO '%:%: Dataset is prepared: %', sp_name, log_timestamp, tot_rec;

	TRUNCATE TABLE fs_dw.fct_wo_backlog_fs;

	INSERT INTO fs_dw.fct_wo_backlog_fs
	SELECT
		fct_wo_backlog_key,
		source_system_key,
		part_key,
		site_key,
		part_site_key,
		source_system_part_number,
		source_system_site_code,
		shortfall_quantity,
		shortfall_value,
		quantity_outstanding,
		committed_shortfall_quantity,
		committed_shortfall_value,
		uncommitted_shortfall_quantity,
		uncommitted_shortfall_value,
		isdeleted_record,
		record_insert_datetime,
		record_update_datetime,
		job_run_id,
		part_hash_key,
		site_hash_key,
		part_site_hash_key,
		delete_hash_key,
		stock_location
	FROM #tmp_backlog_inc;

	GET DIAGNOSTICS rec_count := ROW_COUNT;
	RAISE INFO '%:%: INSERTED Dataset into fct_wo_backlog_fs: %', sp_name, log_timestamp, rec_count;

	UPDATE fs_dw.fct_wo_backlog_fs SET part_key = part.part_key FROM fs_dw.dim_part_fs part WHERE part.part_hash_key = fct_wo_backlog_fs.part_hash_key;
	UPDATE fs_dw.fct_wo_backlog_fs SET site_key = site.site_key FROM common_dw.dim_site_flat site WHERE UPPER(site.source_system_name) || UPPER(site.site_code) = 'MERIDIAN' || source_system_site_code and source_system_site_code <> '';
	UPDATE fs_dw.fct_wo_backlog_fs SET part_site_key = ps.part_site_key FROM fs_dw.dim_part_site_fs ps WHERE ps.part_site_hash_key = fct_wo_backlog_fs.part_site_hash_key;

	RAISE INFO '%:%: UPDATED part_key, site_key, part_site_key to latest in fct_wo_backlog_fs', sp_name, log_timestamp;

	/* UPDATE Keys for fct_wo_backlog_weekly_snapshot_fs (This table gets loaded weekly hence updating the keys here)*/
	UPDATE fs_dw.fct_wo_backlog_weekly_snapshot_fs SET part_key = part.part_key FROM fs_dw.dim_part_fs part WHERE part.part_hash_key = fct_wo_backlog_weekly_snapshot_fs.part_hash_key;
	UPDATE fs_dw.fct_wo_backlog_weekly_snapshot_fs SET site_key = site.site_key FROM common_dw.dim_site_flat site WHERE UPPER(site.source_system_name) || UPPER(site.site_code) = 'MERIDIAN' || source_system_site_code and source_system_site_code <> '';
	UPDATE fs_dw.fct_wo_backlog_weekly_snapshot_fs SET part_site_key = ps.part_site_key FROM fs_dw.dim_part_site_fs ps WHERE ps.part_site_hash_key = fct_wo_backlog_weekly_snapshot_fs.part_site_hash_key;

	RAISE INFO '%:%: Stored Procedure - FINISHED', sp_name, log_timestamp;

	EXCEPTION
	WHEN OTHERS THEN
		   RAISE EXCEPTION 'Error : %',
	SQLERRM ;

	--DROP TABLE IF EXISTS #tmp_backlog_inc;
END;
$$;


create procedure fs_dw.usp_load_fct_wo_backlog_weekly_snapshot_fs(job_run_key integer)
    language plpgsql
as
$$
DECLARE
	sp_name					varchar :=		'';
	log_timestamp			timestamp := CONVERT_TIMEZONE('CST6CDT', SYSDATE);
	max_backlog_snapshot_key bigint := 0;
	rec_count INT;
	tot_rec INT;
	v_SourceSystemKey INT;
	execution_timestamp		timestamp := CONVERT_TIMEZONE('CST6CDT', SYSDATE);
	v_snapshot_date			INTEGER := case when datepart('day',sysdate) = 1 then CAST(to_char(CONVERT_TIMEZONE('CST6CDT', SYSDATE-1),'YYYYMMDD') AS INTEGER) else CAST(to_char(CONVERT_TIMEZONE('CST6CDT', SYSDATE),'YYYYMMDD') AS INTEGER) end;
BEGIN

	sp_name := 'fs_dw.usp_load_fct_wo_backlog_weekly_snapshot_fs';
	RAISE INFO '%: Stored Procedure % starts Execution', log_timestamp, sp_name;

	SELECT source_system_key into v_SourceSystemKey FROM common_ods.lkp_source_system WHERE source_system_name = 'MERIDIAN_FS';

	SELECT NVL(MAX(fct_wo_backlog_snapshot_key),max_backlog_snapshot_key) into max_backlog_snapshot_key FROM fs_dw.fct_wo_backlog_weekly_snapshot_fs;

	/* delete today's snapshot data in event of failure and re-run*/
	delete from fs_dw.fct_wo_backlog_weekly_snapshot_fs where snapshot_date = v_snapshot_date;

	INSERT INTO fs_dw.fct_wo_backlog_weekly_snapshot_fs
	SELECT	max_backlog_snapshot_key + ROW_NUMBER() OVER (order by 1) AS fct_wo_backlog_snapshot_key,
			v_snapshot_date AS snapshot_date,
			source_system_key,
			part_key,
			site_key,
			part_site_key,
			source_system_part_number,
			source_system_site_code,
			shortfall_quantity,
			shortfall_value,
			quantity_outstanding,
			committed_shortfall_quantity,
			committed_shortfall_value,
			uncommitted_shortfall_quantity,
			uncommitted_shortfall_value,
			execution_timestamp AS record_insert_datetime,
			execution_timestamp AS record_update_datetime,
			job_run_key AS job_run_id,
			part_hash_key,
			site_hash_key,
			part_site_hash_key,
			slow_mover_indicator,
			stock_location
	FROM fs_dw.fct_wo_backlog_fs
	WHERE isdeleted_record = 'N';

	SELECT count(*) INTO tot_rec FROM fs_dw.fct_wo_backlog_fs WHERE isdeleted_record = 'N';
	RAISE INFO '%:%: INSERTED dataset into fs_dw.fct_wo_backlog_weekly_snapshot_fs: %', sp_name, log_timestamp, tot_rec;

	UPDATE fs_dw.fct_wo_backlog_weekly_snapshot_fs SET part_key = part.part_key FROM fs_dw.dim_part_fs part WHERE part.part_hash_key = fct_wo_backlog_weekly_snapshot_fs.part_hash_key;
	UPDATE fs_dw.fct_wo_backlog_weekly_snapshot_fs SET site_key = site.site_key FROM common_dw.dim_site_flat site WHERE UPPER(site.source_system_name) || UPPER(site.site_code) = 'MERIDIAN' || source_system_site_code and source_system_site_code <> '';
	UPDATE fs_dw.fct_wo_backlog_weekly_snapshot_fs SET part_site_key = ps.part_site_key FROM fs_dw.dim_part_site_fs ps WHERE ps.part_site_hash_key = fct_wo_backlog_weekly_snapshot_fs.part_site_hash_key;

	RAISE INFO '%:%: UPDATED part_key, site_key, part_site_key to latest in fct_wo_backlog_weekly_snapshot_fs', sp_name, log_timestamp;
	RAISE INFO '%:%: Stored Procedure - FINISHED', sp_name, log_timestamp;

	EXCEPTION
	WHEN OTHERS THEN
		   RAISE EXCEPTION 'Error : %',
	SQLERRM ;

END;
$$;
