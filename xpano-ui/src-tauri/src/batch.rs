use crate::contracts::{
    BatchError, BatchProgress, BatchQueueFile, BatchQueueState, BatchStageStatus,
    BatchStageStatuses, BatchTask, BatchTaskState, BATCH_QUEUE_SCHEMA_VERSION,
};
#[cfg(test)]
use crate::contracts::{BatchPipelineInput, BatchStages};
use crate::project::{write_json_value_atomic, ProjectCommandError};
use chrono::{SecondsFormat, Utc};
use std::collections::HashSet;
use std::path::{Path, PathBuf};
use std::sync::{atomic::{AtomicU8, Ordering}, Arc};
use std::thread;
use std::time::Duration;
use tauri::{AppHandle, Manager, State};
use uuid::Uuid;

const BATCH_DIRECTORY: &str = "batch";
const BATCH_QUEUE_FILE: &str = "queue.json";
const SIGNAL_RUNNING: u8 = 0;
const SIGNAL_STOP: u8 = 1;
const SIGNAL_SHUTDOWN: u8 = 2;

fn now_iso() -> String {
    Utc::now().to_rfc3339_opts(SecondsFormat::Millis, true)
}

fn batch_error(code: &str, message: impl Into<String>) -> ProjectCommandError {
    ProjectCommandError::new(code, message)
}

pub(crate) fn observe_job_event(app: &AppHandle, event: &crate::contracts::JobEvent) {
    let Some(task_id) = event.task_id.as_deref() else { return };
    let Some(state) = app.try_state::<crate::AppState>() else { return };
    let Ok(mut coordinator) = state.batch.lock() else { return };
    if coordinator.ensure_loaded(app).is_err() { return; }
    let Some(queue) = coordinator.queue.as_mut() else { return };
    let Some(task) = queue.tasks.iter_mut().find(|task| task.task_id == task_id) else { return };
    let (stage, index) = match event.workspace {
        crate::contracts::ProjectWorkspace::Media => ("media", 0.0),
        crate::contracts::ProjectWorkspace::Reconstruction => ("reconstruction", 1.0),
        crate::contracts::ProjectWorkspace::Training => ("training", 2.0),
        crate::contracts::ProjectWorkspace::Results => return,
    };
    let stage_count = [task.stages.media, task.stages.reconstruction, task.stages.training].into_iter().filter(|enabled| *enabled).count().max(1) as f64;
    let stage_percent = event.percent.unwrap_or_else(|| if event.state == crate::contracts::JobState::Completed { 100.0 } else { 0.0 }).clamp(0.0, 100.0);
    task.progress.percent = ((index * 100.0 + stage_percent) / stage_count).clamp(0.0, 100.0);
    task.progress.message = event.message.clone();
    task.progress.current = event.current;
    task.progress.total = event.total;
    task.progress.eta_seconds = event.eta_seconds;
    task.progress.elapsed_seconds = task.started_at.as_deref()
        .and_then(|value| chrono::DateTime::parse_from_rfc3339(value).ok())
        .map(|started| Utc::now().signed_duration_since(started.with_timezone(&Utc)).num_seconds().max(0) as u64)
        .unwrap_or(task.progress.elapsed_seconds);
    task.current_stage = Some(stage.to_string());
}

pub(crate) fn queue_path(app: &AppHandle) -> Result<PathBuf, ProjectCommandError> {
    let root = app.path().app_local_data_dir().map_err(|error| {
        batch_error("invalid_project", format!("failed to resolve batch data directory: {error}"))
    })?;
    Ok(root.join(BATCH_DIRECTORY).join(BATCH_QUEUE_FILE))
}

impl BatchQueueFile {
    pub fn empty() -> Self {
        Self {
            schema_version: BATCH_QUEUE_SCHEMA_VERSION,
            revision: 0,
            state: BatchQueueState::Idle,
            active_task_id: None,
            tasks: Vec::new(),
        }
    }

    pub fn validate(&self) -> Result<(), ProjectCommandError> {
        if self.schema_version != BATCH_QUEUE_SCHEMA_VERSION {
            return Err(batch_error(
                "artifact_corrupt",
                format!("unsupported batch queue schema version: {}", self.schema_version),
            ));
        }
        let mut task_ids = HashSet::new();
        let mut orders = HashSet::new();
        let mut active_count = 0usize;
        for task in &self.tasks {
            if task.task_id.trim().is_empty()
                || task.project_id.trim().is_empty()
                || task.project_root.trim().is_empty()
                || task.label.trim().is_empty()
            {
                return Err(batch_error("artifact_corrupt", "batch task identity is incomplete"));
            }
            if !task_ids.insert(task.task_id.as_str()) {
                return Err(batch_error("artifact_corrupt", "batch queue contains duplicate task ids"));
            }
            if !orders.insert(task.order) {
                return Err(batch_error("artifact_corrupt", "batch queue contains duplicate task order"));
            }
            task.stages
                .validate_prefix()
                .map_err(|error| batch_error("invalid_project", error))?;
            if task.stage_status.media == BatchStageStatus::Disabled && task.stages.media
                || task.stage_status.reconstruction == BatchStageStatus::Disabled && task.stages.reconstruction
                || task.stage_status.training == BatchStageStatus::Disabled && task.stages.training
            {
                return Err(batch_error("artifact_corrupt", "batch stage status disagrees with enabled stages"));
            }
            if matches!(task.state, BatchTaskState::Running) {
                active_count += 1;
            }
        }
        if active_count > 1 {
            return Err(batch_error("artifact_corrupt", "batch queue has more than one running task"));
        }
        if let Some(active) = self.active_task_id.as_deref() {
            let task = self.tasks.iter().find(|task| task.task_id == active).ok_or_else(|| {
                batch_error("artifact_corrupt", "batch active task does not exist")
            })?;
            if !matches!(task.state, BatchTaskState::Running | BatchTaskState::Cancelled | BatchTaskState::Interrupted) {
                return Err(batch_error("artifact_corrupt", "batch active task has an invalid state"));
            }
        }
        if self.state == BatchQueueState::Idle && self.active_task_id.is_some() {
            return Err(batch_error("artifact_corrupt", "idle batch queue cannot have an active task"));
        }
        Ok(())
    }

    pub fn sort_by_order(&mut self) {
        self.tasks.sort_by_key(|task| task.order);
    }

    fn bump_revision(&mut self) {
        self.revision = self.revision.saturating_add(1);
    }

    pub fn upsert(&mut self, mut task: BatchTask) -> Result<BatchTask, ProjectCommandError> {
        task.stages
            .validate_prefix()
            .map_err(|error| batch_error("invalid_project", error))?;
        if task.task_id.trim().is_empty() {
            task.task_id = Uuid::new_v4().to_string();
        }
        if task.project_id.trim().is_empty() || task.project_root.trim().is_empty() || task.label.trim().is_empty() {
            return Err(batch_error("invalid_project", "batch task requires project, root, and label"));
        }
        let timestamp = now_iso();
        if task.created_at.trim().is_empty() {
            task.created_at = timestamp.clone();
        }
        task.updated_at = timestamp;
        if let Some(existing) = self.tasks.iter_mut().find(|item| item.task_id == task.task_id) {
            if matches!(existing.state, BatchTaskState::Queued | BatchTaskState::Running) {
                return Err(batch_error("job_conflict", "queued or running batch task cannot be edited"));
            }
            task.order = existing.order;
            task.state = existing.state;
            task.stage_status = if matches!(task.state, BatchTaskState::Draft) {
                BatchStageStatuses::for_stages(&task.stages)
            } else {
                existing.stage_status.clone()
            };
            *existing = task.clone();
        } else {
            task.order = self.tasks.iter().map(|item| item.order).max().map_or(0, |order| order.saturating_add(1));
            task.stage_status = BatchStageStatuses::for_stages(&task.stages);
            self.tasks.push(task.clone());
        }
        self.bump_revision();
        self.sort_by_order();
        Ok(task)
    }

    pub fn enqueue(&mut self, task_id: &str) -> Result<BatchTask, ProjectCommandError> {
        let updated = {
            let task = self.tasks.iter_mut().find(|task| task.task_id == task_id).ok_or_else(|| {
                batch_error("invalid_project", "batch task does not exist")
            })?;
            if matches!(task.state, BatchTaskState::Running | BatchTaskState::Queued) {
                return Ok(task.clone());
            }
            if matches!(task.state, BatchTaskState::Completed) {
                return Err(batch_error("job_conflict", "completed task must be duplicated before enqueueing"));
            }
            task.stages
                .validate_prefix()
                .map_err(|error| batch_error("invalid_project", error))?;
            task.state = BatchTaskState::Queued;
            task.current_stage = None;
            task.stage_status = BatchStageStatuses::for_stages(&task.stages);
            task.progress = BatchProgress::default();
            task.last_error = None;
            task.stage_job_ids.clear();
            task.started_at = None;
            task.finished_at = None;
            task.updated_at = now_iso();
            task.clone()
        };
        self.bump_revision();
        Ok(updated)
    }

    pub fn remove(&mut self, task_id: &str) -> Result<(), ProjectCommandError> {
        let index = self.tasks.iter().position(|task| task.task_id == task_id).ok_or_else(|| {
            batch_error("invalid_project", "batch task does not exist")
        })?;
        if matches!(self.tasks[index].state, BatchTaskState::Queued | BatchTaskState::Running) {
            return Err(batch_error("job_conflict", "queued or running batch task cannot be removed"));
        }
        self.tasks.remove(index);
        for (index, task) in self.tasks.iter_mut().enumerate() {
            task.order = index as u64;
            task.updated_at = now_iso();
        }
        self.bump_revision();
        Ok(())
    }

    pub fn reorder(&mut self, task_ids: &[String]) -> Result<(), ProjectCommandError> {
        if task_ids.len() != self.tasks.len() {
            return Err(batch_error("invalid_project", "batch reorder must include every task exactly once"));
        }
        let expected = self.tasks.iter().map(|task| task.task_id.as_str()).collect::<HashSet<_>>();
        let received = task_ids.iter().map(String::as_str).collect::<HashSet<_>>();
        if expected != received || received.len() != task_ids.len() {
            return Err(batch_error("invalid_project", "batch reorder contains unknown or duplicate task ids"));
        }
        for (order, task_id) in task_ids.iter().enumerate() {
            let task = self.tasks.iter_mut().find(|task| task.task_id == *task_id).unwrap();
            if matches!(task.state, BatchTaskState::Running) {
                return Err(batch_error("job_conflict", "running batch task cannot be reordered"));
            }
            task.order = order as u64;
            task.updated_at = now_iso();
        }
        self.bump_revision();
        self.sort_by_order();
        Ok(())
    }

    pub fn mark_queue_state(&mut self, state: BatchQueueState, active_task_id: Option<String>) -> Result<(), ProjectCommandError> {
        if state == BatchQueueState::Idle && active_task_id.is_some() {
            return Err(batch_error("invalid_project", "idle batch queue cannot have an active task"));
        }
        self.state = state;
        self.active_task_id = active_task_id;
        self.bump_revision();
        self.validate()
    }

    pub fn mark_task_running(&mut self, task_id: &str, stage: &str) -> Result<(), ProjectCommandError> {
        if self.tasks.iter().any(|task| matches!(task.state, BatchTaskState::Running)) {
            return Err(batch_error("job_conflict", "another batch task is already running"));
        }
        let task = self.tasks.iter_mut().find(|task| task.task_id == task_id).ok_or_else(|| {
            batch_error("invalid_project", "batch task does not exist")
        })?;
        if !matches!(task.state, BatchTaskState::Queued) {
            return Err(batch_error("job_conflict", "only queued tasks can start"));
        }
        task.state = BatchTaskState::Running;
        task.current_stage = Some(stage.to_string());
        task.started_at = Some(now_iso());
        task.updated_at = now_iso();
        self.active_task_id = Some(task_id.to_string());
        self.state = BatchQueueState::Running;
        self.bump_revision();
        self.validate()
    }

    pub fn mark_task_finished(&mut self, task_id: &str, state: BatchTaskState, error: Option<BatchError>) -> Result<(), ProjectCommandError> {
        if !matches!(state, BatchTaskState::Completed | BatchTaskState::Failed | BatchTaskState::Cancelled | BatchTaskState::Interrupted) {
            return Err(batch_error("invalid_project", "invalid batch terminal state"));
        }
        let task = self.tasks.iter_mut().find(|task| task.task_id == task_id).ok_or_else(|| {
            batch_error("invalid_project", "batch task does not exist")
        })?;
        if state != BatchTaskState::Completed {
            match task.current_stage.as_deref() {
                Some("media") => task.stage_status.media = BatchStageStatus::Failed,
                Some("reconstruction") => task.stage_status.reconstruction = BatchStageStatus::Failed,
                Some("training") => task.stage_status.training = BatchStageStatus::Failed,
                _ => {}
            }
        }
        task.state = state;
        task.current_stage = None;
        task.last_error = error;
        task.finished_at = Some(now_iso());
        task.updated_at = now_iso();
        if self.active_task_id.as_deref() == Some(task_id) {
            self.active_task_id = None;
        }
        if self.state != BatchQueueState::Stopping {
            self.state = if self.tasks.iter().any(|item| item.state == BatchTaskState::Queued) {
                BatchQueueState::Running
            } else {
                BatchQueueState::Idle
            };
        }
        self.bump_revision();
        self.validate()
    }

    fn interrupt_active_for_shutdown(&mut self) -> Result<(), ProjectCommandError> {
        if let Some(task_id) = self.active_task_id.clone() {
            let task = self.tasks.iter_mut().find(|task| task.task_id == task_id).ok_or_else(|| {
                batch_error("artifact_corrupt", "batch active task does not exist")
            })?;
            if task.state == BatchTaskState::Running {
                let stage = task.current_stage.clone();
                match stage.as_deref() {
                    Some("media") => task.stage_status.media = BatchStageStatus::Failed,
                    Some("reconstruction") => task.stage_status.reconstruction = BatchStageStatus::Failed,
                    Some("training") => task.stage_status.training = BatchStageStatus::Failed,
                    _ => {}
                }
                task.state = BatchTaskState::Interrupted;
                task.current_stage = None;
                task.last_error = Some(BatchError {
                    code: "app_shutdown".to_string(),
                    stage,
                    message: "应用关闭，当前任务已中断".to_string(),
                });
                task.finished_at = Some(now_iso());
                task.updated_at = now_iso();
            }
        }
        self.state = BatchQueueState::Idle;
        self.active_task_id = None;
        self.bump_revision();
        self.validate()
    }

}

pub(crate) struct BatchCoordinator {
    queue: Option<BatchQueueFile>,
    path: Option<PathBuf>,
    stop_signal: Option<Arc<AtomicU8>>,
}

pub(crate) fn ensure_manual_startable(app: &AppHandle, state: &crate::AppState) -> Result<(), ProjectCommandError> {
    let mut coordinator = state.batch.lock().map_err(|error| batch_error("job_conflict", error.to_string()))?;
    coordinator.ensure_loaded(app)?;
    if coordinator.queue.as_ref().is_some_and(|queue| matches!(queue.state, BatchQueueState::Running | BatchQueueState::Stopping)) {
        return Err(batch_error("batch_queue_active", "批量队列正在运行，请先停止队列后再启动手动任务"));
    }
    Ok(())
}

impl Default for BatchCoordinator {
    fn default() -> Self {
        Self { queue: None, path: None, stop_signal: None }
    }
}

fn save_queue(app: &AppHandle, state: &crate::AppState, mutate: impl FnOnce(&mut BatchQueueFile) -> Result<(), ProjectCommandError>) -> Result<BatchQueueFile, ProjectCommandError> {
    let mut coordinator = state.batch.lock().map_err(|error| batch_error("job_conflict", error.to_string()))?;
    let queue = coordinator.queue_mut(app)?;
    mutate(queue)?;
    coordinator.persist()?;
    Ok(coordinator.queue.as_ref().unwrap().clone())
}

fn mark_stage(app: &AppHandle, state: &crate::AppState, task_id: &str, stage: &str, status: BatchStageStatus, message: &str, percent: f64) -> Result<(), ProjectCommandError> {
    save_queue(app, state, |queue| {
        let task = queue.tasks.iter_mut().find(|task| task.task_id == task_id).ok_or_else(|| batch_error("invalid_project", "batch task does not exist"))?;
        task.current_stage = (status == BatchStageStatus::Running).then(|| stage.to_string());
        match stage { "media" => task.stage_status.media = status, "reconstruction" => task.stage_status.reconstruction = status, "training" => task.stage_status.training = status, _ => {} }
        task.progress.percent = percent.clamp(0.0, 100.0);
        task.progress.message = message.to_string();
        task.progress.elapsed_seconds = task.started_at.as_deref()
            .and_then(|value| chrono::DateTime::parse_from_rfc3339(value).ok())
            .map(|started| Utc::now().signed_duration_since(started.with_timezone(&Utc)).num_seconds().max(0) as u64)
            .unwrap_or(task.progress.elapsed_seconds);
        task.updated_at = now_iso();
        Ok(())
    }).map(|_| ())
}

fn record_stage_job_id(app: &AppHandle, state: &crate::AppState, task_id: &str, stage: &str, job_id: &str) -> Result<(), ProjectCommandError> {
    save_queue(app, state, |queue| {
        let task = queue.tasks.iter_mut().find(|task| task.task_id == task_id).ok_or_else(|| batch_error("invalid_project", "batch task does not exist"))?;
        task.stage_job_ids.insert(stage.to_string(), serde_json::Value::String(job_id.to_string()));
        task.updated_at = now_iso();
        Ok(())
    }).map(|_| ())
}

fn latest_job_id(project_root: &Path, workspace: crate::contracts::ProjectWorkspace) -> Result<String, ProjectCommandError> {
    crate::job::get_job_snapshots_impl(project_root)?
        .into_iter()
        .rev()
        .find(|snapshot| snapshot.workspace == workspace)
        .map(|snapshot| snapshot.job_id)
        .ok_or_else(|| batch_error("artifact_corrupt", "stage started without a registered job"))
}

fn terminal_state_for_stop(signal: &Arc<AtomicU8>) -> BatchTaskState {
    match signal.load(Ordering::SeqCst) {
        SIGNAL_STOP => BatchTaskState::Cancelled,
        SIGNAL_SHUTDOWN => BatchTaskState::Interrupted,
        _ => BatchTaskState::Failed,
    }
}

fn validate_task_project(
    task: &BatchTask,
    project: &crate::contracts::XpanoProjectV2,
) -> Result<(), ProjectCommandError> {
    if task.project_id != project.project_id {
        return Err(batch_error("invalid_project", "任务绑定的工程已被替换，请重新保存任务"));
    }
    if task.configured_revision != project.revision {
        return Err(ProjectCommandError::revision_conflict(
            task.configured_revision,
            project.revision,
        ));
    }
    Ok(())
}

fn completed_stage_percent(task: &BatchTask, stage: &str) -> f64 {
    let enabled = [task.stages.media, task.stages.reconstruction, task.stages.training]
        .into_iter()
        .filter(|value| *value)
        .count()
        .max(1) as f64;
    let completed = match stage {
        "media" => 1.0,
        "reconstruction" => 2.0,
        "training" => 3.0,
        _ => 0.0,
    };
    (completed * 100.0 / enabled).clamp(0.0, 100.0)
}

fn default_reconstruction_args(project_root: &Path) -> Result<Vec<String>, ProjectCommandError> {
    let project = crate::project::read_project(project_root)?;
    let config = &project.reconstruction.config;
    let manifest = config
        .get("mediaManifestPath")
        .and_then(serde_json::Value::as_str)
        .filter(|value| !value.trim().is_empty())
        .ok_or_else(|| batch_error("invalid_project", "工程缺少素材 manifest，请先完成素材准备"))?;
    let manifest_path = Path::new(manifest);
    let manifest_path = if manifest_path.is_absolute() {
        manifest_path.to_path_buf()
    } else {
        project_root.join(manifest_path)
    };
    let mut args = vec![
        "--output".to_string(),
        project_root.to_string_lossy().to_string(),
        "--frames-per-second".to_string(),
        "1".to_string(),
        "--manifest".to_string(),
        manifest_path.to_string_lossy().to_string(),
        "--skip-extract".to_string(),
    ];
    let string_value = |key: &str, fallback: &str| {
        config.get(key).and_then(serde_json::Value::as_str).unwrap_or(fallback).to_string()
    };
    let number_value = |key: &str, fallback: u64| {
        config.get(key).and_then(serde_json::Value::as_u64).unwrap_or(fallback).to_string()
    };
    match project.reconstruction.backend {
        crate::contracts::ReconstructionBackend::Metashape => {
            if let Some(path) = config.get("metashapePath").and_then(serde_json::Value::as_str).filter(|value| !value.trim().is_empty()) {
                args.extend(["--metashape".to_string(), path.to_string()]);
            }
            args.extend([
                "--metashape-alignment-mode".to_string(), string_value("alignmentMode", "backbone"),
                "--metashape-keypoint-limit".to_string(), number_value("metashapeKeypointLimit", 40000),
                "--metashape-tiepoint-limit".to_string(), number_value("metashapeTiepointLimit", 0),
            ]);
        }
        crate::contracts::ReconstructionBackend::Colmap => {
            args.extend([
                "--backend".to_string(), "colmap".to_string(),
                "--colmap-density-preset".to_string(), string_value("colmapDensityPreset", "stable"),
                "--colmap-matcher".to_string(), string_value("colmapMatcher", "sequential"),
                "--colmap-max-image-size".to_string(), number_value("colmapMaxImageSize", 1600),
                "--colmap-max-num-features".to_string(), number_value("colmapMaxNumFeatures", 4096),
            ]);
            if config.get("colmapUseGpu").and_then(serde_json::Value::as_bool).unwrap_or(true) {
                args.push("--colmap-use-gpu".to_string());
            }
        }
    }
    args.extend(["--up-axis".to_string(), string_value("upAxis", "+Y")]);
    Ok(args)
}

fn wait_for_stage(state: &crate::AppState, task: &BatchTask, stage: &str, job_id: &str, signal: &Arc<AtomicU8>) -> Result<(), ProjectCommandError> {
    let root = Path::new(&task.project_root);
    let started = std::time::Instant::now();
    loop {
        if signal.load(Ordering::SeqCst) != SIGNAL_RUNNING {
            let _ = state.pipeline.lock().map(|mut pipeline| pipeline.cancel());
            return Err(batch_error("job_conflict", "batch task cancelled"));
        }
        let pipeline_running = state.pipeline.lock().map(|pipeline| pipeline.is_running()).unwrap_or(false);
        let snapshots = crate::job::get_job_snapshots_impl(root)?;
        let snapshot = snapshots.iter().find(|snapshot| snapshot.job_id == job_id).ok_or_else(|| {
            batch_error("artifact_corrupt", format!("{stage} job snapshot is missing"))
        })?;
        match snapshot.state {
            crate::contracts::JobState::Completed if !pipeline_running => return Ok(()),
            crate::contracts::JobState::Failed | crate::contracts::JobState::Cancelled | crate::contracts::JobState::Interrupted if !pipeline_running => return Err(batch_error("backend_unavailable", format!("{stage} stage ended with {:?}", snapshot.state))),
            _ => {}
        }
        if started.elapsed() > Duration::from_secs(5) && !pipeline_running {
            return Err(batch_error("backend_unavailable", format!("{stage} stage stopped without a completed job")));
        }
        thread::sleep(Duration::from_millis(500));
    }
}

fn run_batch_worker(app: AppHandle, signal: Arc<AtomicU8>) {
    loop {
        if signal.load(Ordering::SeqCst) != SIGNAL_RUNNING { break; }
        let state = app.state::<crate::AppState>();
        let task = {
            let mut coordinator = match state.batch.lock() { Ok(value) => value, Err(_) => break };
            let queue = match coordinator.queue_mut(&app) { Ok(value) => value, Err(_) => break };
            let Some(task) = queue.tasks.iter().find(|task| task.state == BatchTaskState::Queued).cloned() else {
                let _ = queue.mark_queue_state(BatchQueueState::Idle, None);
                let _ = coordinator.persist();
                break;
            };
            let stage = if task.stages.media { "media" } else if task.stages.reconstruction { "reconstruction" } else { "training" };
            if queue.mark_task_running(&task.task_id, stage).is_err() || coordinator.persist().is_err() { break; }
            task
        };
        let current = crate::project::read_project(Path::new(&task.project_root));
        let mut failed_stage = task.current_stage.clone();
        let result = current.and_then(|project| {
            validate_task_project(&task, &project)?;
            let expected = task.configured_revision;
            let mut stage_percent = 0.0;
            if task.stages.media {
                failed_stage = Some("media".to_string());
                mark_stage(&app, &state, &task.task_id, "media", BatchStageStatus::Running, "正在准备素材", stage_percent)?;
                let target_track_ids = if task.pipeline.media_track_ids.is_empty() {
                    project.tracks.iter().map(|track| track.id.clone()).collect()
                } else {
                    task.pipeline.media_track_ids.clone()
                };
                crate::media::start_media_job_blocking(&app, state.inner(), task.project_root.clone(), expected, target_track_ids, Some(task.task_id.clone()))?;
                let job_id = latest_job_id(Path::new(&task.project_root), crate::contracts::ProjectWorkspace::Media)?;
                record_stage_job_id(&app, state.inner(), &task.task_id, "media", &job_id)?;
                wait_for_stage(state.inner(), &task, "media", &job_id, &signal)?;
                stage_percent = completed_stage_percent(&task, "media");
                mark_stage(&app, state.inner(), &task.task_id, "media", BatchStageStatus::Completed, "素材准备完成", stage_percent)?;
            }
            if task.stages.reconstruction {
                failed_stage = Some("reconstruction".to_string());
                mark_stage(&app, state.inner(), &task.task_id, "reconstruction", BatchStageStatus::Running, "正在对齐重建", stage_percent)?;
                let plan_id = task.pipeline.reconstruction_plan_id.clone().or_else(|| crate::reconstruction::active_execution_plan_impl(Path::new(&task.project_root)).ok().map(|plan| plan.plan_id)).ok_or_else(|| batch_error("invalid_project", "工程中没有可用的对齐计划"))?;
                let python = task.pipeline.reconstruction_python_exe.clone().unwrap_or_else(|| crate::tool_resolver::resolve_python(""));
                let script = task.pipeline.reconstruction_script.clone().unwrap_or_else(|| "scripts/run_xpano_tracks_job.py".to_string());
                let reconstruction_args = if task.pipeline.reconstruction_args.is_empty() { default_reconstruction_args(Path::new(&task.project_root))? } else { task.pipeline.reconstruction_args.clone() };
                crate::start_reconstruction_job_blocking(app.clone(), task.project_root.clone(), crate::project::read_project(Path::new(&task.project_root))?.revision, plan_id, python, script, reconstruction_args, Some(task.task_id.clone()))?;
                let job_id = latest_job_id(Path::new(&task.project_root), crate::contracts::ProjectWorkspace::Reconstruction)?;
                record_stage_job_id(&app, state.inner(), &task.task_id, "reconstruction", &job_id)?;
                wait_for_stage(state.inner(), &task, "reconstruction", &job_id, &signal)?;
                stage_percent = completed_stage_percent(&task, "reconstruction");
                mark_stage(&app, state.inner(), &task.task_id, "reconstruction", BatchStageStatus::Completed, "对齐重建完成", stage_percent)?;
            }
            if task.stages.training {
                failed_stage = Some("training".to_string());
                mark_stage(&app, state.inner(), &task.task_id, "training", BatchStageStatus::Running, "正在进行高斯训练", stage_percent)?;
                let config = task.pipeline.training_config.clone().unwrap_or_default();
                let mut merged = serde_json::to_value(crate::training::TrainingConfig::default()).map_err(|error| batch_error("invalid_training_config", error.to_string()))?;
                if let (Some(base), Some(overrides)) = (merged.as_object_mut(), config.as_object()) {
                    for (key, value) in overrides { base.insert(key.clone(), value.clone()); }
                }
                let config: crate::training::TrainingConfig = serde_json::from_value(merged).map_err(|error| batch_error("invalid_training_config", error.to_string()))?;
                crate::start_training_job_blocking(app.clone(), task.project_root.clone(), crate::project::read_project(Path::new(&task.project_root))?.revision, config, Some(task.task_id.clone()))?;
                let job_id = latest_job_id(Path::new(&task.project_root), crate::contracts::ProjectWorkspace::Training)?;
                record_stage_job_id(&app, state.inner(), &task.task_id, "training", &job_id)?;
                wait_for_stage(state.inner(), &task, "training", &job_id, &signal)?;
                mark_stage(&app, state.inner(), &task.task_id, "training", BatchStageStatus::Completed, "高斯训练完成", completed_stage_percent(&task, "training"))?;
            }
            Ok(())
        });
        let terminal = match result { Ok(()) => (BatchTaskState::Completed, None), Err(error) => (terminal_state_for_stop(&signal), Some(BatchError { code: error.code, stage: failed_stage, message: error.message })) };
        if save_queue(&app, state.inner(), |queue| queue.mark_task_finished(&task.task_id, terminal.0, terminal.1)).is_err() {
            break;
        }
    }
    let state = app.state::<crate::AppState>();
    let _ = save_queue(&app, state.inner(), |queue| {
        queue.state = BatchQueueState::Idle;
        queue.active_task_id = None;
        queue.bump_revision();
        Ok(())
    });
}

#[tauri::command]
pub fn start_batch_queue(app: AppHandle, state: State<'_, crate::AppState>) -> Result<BatchQueueFile, ProjectCommandError> {
    let signal = Arc::new(AtomicU8::new(SIGNAL_RUNNING));
    let queue = {
        let mut coordinator = state.batch.lock().map_err(|error| batch_error("job_conflict", error.to_string()))?;
        let pipeline = state.pipeline.lock().map_err(|error| batch_error("job_conflict", error.to_string()))?;
        pipeline.ensure_startable().map_err(|error| batch_error("job_conflict", error))?;
        let queue = coordinator.queue_mut(&app)?;
        if queue.state != BatchQueueState::Idle { return Err(batch_error("job_conflict", "batch queue is already running")); }
        if !queue.tasks.iter().any(|task| task.state == BatchTaskState::Queued) { return Err(batch_error("invalid_project", "no queued batch task")); }
        queue.state = BatchQueueState::Running;
        queue.bump_revision();
        let snapshot = queue.clone();
        coordinator.stop_signal = Some(signal.clone());
        coordinator.persist()?;
        snapshot
    };
    thread::spawn(move || run_batch_worker(app, signal));
    Ok(queue)
}

#[tauri::command]
pub fn stop_batch_queue(app: AppHandle, state: State<'_, crate::AppState>) -> Result<BatchQueueFile, ProjectCommandError> {
    if let Ok(coordinator) = state.batch.lock() { if let Some(signal) = &coordinator.stop_signal { signal.store(SIGNAL_STOP, Ordering::SeqCst); } }
    if let Ok(mut pipeline) = state.pipeline.lock() { let _ = pipeline.cancel(); }
    save_queue(&app, state.inner(), |queue| {
        if queue.state == BatchQueueState::Idle {
            return Err(batch_error("job_conflict", "batch queue is not running"));
        }
        queue.state = BatchQueueState::Stopping;
        queue.bump_revision();
        Ok(())
    })
}

pub(crate) fn interrupt_for_shutdown(app: &AppHandle, state: &crate::AppState) {
    let Ok(mut coordinator) = state.batch.lock() else { return };
    if coordinator.ensure_loaded(app).is_err() { return; }
    if let Some(signal) = &coordinator.stop_signal {
        signal.store(SIGNAL_SHUTDOWN, Ordering::SeqCst);
    }
    if let Some(queue) = coordinator.queue.as_mut() {
        let _ = queue.interrupt_active_for_shutdown();
    }
    let _ = coordinator.persist();
}

impl BatchCoordinator {
    fn ensure_loaded(&mut self, app: &AppHandle) -> Result<(), ProjectCommandError> {
        let path = queue_path(app)?;
        if self.path.as_ref() != Some(&path) {
            let mut queue = load_queue(&path)?;
            let recovered = queue.state != BatchQueueState::Idle
                || queue.tasks.iter().any(|task| task.state == BatchTaskState::Running);
            if recovered {
                queue.interrupt_active_for_shutdown()?;
            }
            self.queue = Some(queue);
            self.path = Some(path);
            if recovered {
                self.persist()?;
            }
        } else if self.queue.is_none() {
            let mut queue = load_queue(&path)?;
            let recovered = queue.state != BatchQueueState::Idle
                || queue.tasks.iter().any(|task| task.state == BatchTaskState::Running);
            if recovered {
                queue.interrupt_active_for_shutdown()?;
            }
            self.queue = Some(queue);
            if recovered {
                self.persist()?;
            }
        }
        Ok(())
    }

    fn queue_mut(&mut self, app: &AppHandle) -> Result<&mut BatchQueueFile, ProjectCommandError> {
        self.ensure_loaded(app)?;
        Ok(self.queue.as_mut().unwrap())
    }

    fn persist(&self) -> Result<(), ProjectCommandError> {
        let path = self.path.as_ref().ok_or_else(|| batch_error("invalid_project", "batch queue is not loaded"))?;
        let queue = self.queue.as_ref().unwrap();
        queue.validate()?;
        let value = serde_json::to_value(queue).map_err(|error| batch_error("artifact_corrupt", error.to_string()))?;
        write_json_value_atomic(path, &value)
    }
}

fn load_queue(path: &Path) -> Result<BatchQueueFile, ProjectCommandError> {
    if !path.is_file() {
        return Ok(BatchQueueFile::empty());
    }
    let payload = std::fs::read(path).map_err(|error| batch_error("artifact_corrupt", format!("failed to read batch queue: {error}")))?;
    let queue: BatchQueueFile = match serde_json::from_slice(&payload) {
        Ok(queue) => queue,
        Err(error) => {
            let backup = path.with_file_name(format!("queue.json.corrupt.{}", Utc::now().timestamp_millis()));
            let _ = std::fs::copy(path, backup);
            return Err(batch_error("artifact_corrupt", format!("failed to parse batch queue: {error}")));
        }
    };
    queue.validate()?;
    Ok(queue)
}

#[cfg(test)]
fn empty_task_template() -> BatchTask {
    let timestamp = now_iso();
    BatchTask {
        task_id: String::new(),
        project_id: String::new(),
        project_root: String::new(),
        label: String::new(),
        order: 0,
        configured_revision: 0,
        stages: BatchStages::default(),
        stage_status: BatchStageStatuses::default(),
        state: BatchTaskState::Draft,
        current_stage: None,
        stage_job_ids: serde_json::Map::new(),
        progress: BatchProgress::default(),
        last_error: None,
        pipeline: BatchPipelineInput::default(),
        created_at: timestamp.clone(),
        started_at: None,
        finished_at: None,
        updated_at: timestamp,
    }
}

#[tauri::command]
pub fn get_batch_queue(
    app: AppHandle,
    state: State<'_, crate::AppState>,
) -> Result<BatchQueueFile, ProjectCommandError> {
    let mut coordinator = state.batch.lock().map_err(|error| batch_error("job_conflict", error.to_string()))?;
    coordinator.ensure_loaded(&app)?;
    Ok(coordinator.queue.as_ref().unwrap().clone())
}

#[tauri::command]
pub fn save_batch_task(
    app: AppHandle,
    state: State<'_, crate::AppState>,
    task: BatchTask,
) -> Result<BatchTask, ProjectCommandError> {
    let mut coordinator = state.batch.lock().map_err(|error| batch_error("job_conflict", error.to_string()))?;
    let saved = coordinator.queue_mut(&app)?.upsert(task)?;
    coordinator.persist()?;
    Ok(saved)
}

#[tauri::command]
pub fn enqueue_batch_task(
    app: AppHandle,
    state: State<'_, crate::AppState>,
    task_id: String,
) -> Result<BatchQueueFile, ProjectCommandError> {
    let mut coordinator = state.batch.lock().map_err(|error| batch_error("job_conflict", error.to_string()))?;
    coordinator.queue_mut(&app)?.enqueue(&task_id)?;
    coordinator.persist()?;
    Ok(coordinator.queue.as_ref().unwrap().clone())
}

#[tauri::command]
pub fn requeue_batch_task(
    app: AppHandle,
    state: State<'_, crate::AppState>,
    task_id: String,
) -> Result<BatchQueueFile, ProjectCommandError> {
    enqueue_batch_task(app, state, task_id)
}

#[tauri::command]
pub fn remove_batch_task(
    app: AppHandle,
    state: State<'_, crate::AppState>,
    task_id: String,
) -> Result<BatchQueueFile, ProjectCommandError> {
    let mut coordinator = state.batch.lock().map_err(|error| batch_error("job_conflict", error.to_string()))?;
    coordinator.queue_mut(&app)?.remove(&task_id)?;
    coordinator.persist()?;
    Ok(coordinator.queue.as_ref().unwrap().clone())
}

#[tauri::command]
pub fn reorder_batch_tasks(
    app: AppHandle,
    state: State<'_, crate::AppState>,
    task_ids: Vec<String>,
) -> Result<BatchQueueFile, ProjectCommandError> {
    let mut coordinator = state.batch.lock().map_err(|error| batch_error("job_conflict", error.to_string()))?;
    coordinator.queue_mut(&app)?.reorder(&task_ids)?;
    coordinator.persist()?;
    Ok(coordinator.queue.as_ref().unwrap().clone())
}

#[tauri::command]
pub fn delete_batch_queue(
    app: AppHandle,
    state: State<'_, crate::AppState>,
) -> Result<(), ProjectCommandError> {
    let mut coordinator = state.batch.lock().map_err(|error| batch_error("job_conflict", error.to_string()))?;
    coordinator.ensure_loaded(&app)?;
    if coordinator.queue.as_ref().unwrap().tasks.iter().any(|task| matches!(task.state, BatchTaskState::Running)) {
        return Err(batch_error("job_conflict", "running batch queue cannot be deleted"));
    }
    let path = coordinator.path.as_ref().unwrap();
    if path.is_file() {
        std::fs::remove_file(path).map_err(|error| batch_error("disk_full", format!("failed to delete batch queue: {error}")))?;
    }
    coordinator.queue = Some(BatchQueueFile::empty());
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn task(stages: BatchStages) -> BatchTask {
        let mut task = empty_task_template();
        task.task_id = Uuid::new_v4().to_string();
        task.project_id = "project-1".to_string();
        task.project_root = "C:/projects/one".to_string();
        task.label = "One".to_string();
        task.stages = stages;
        task.stage_status = BatchStageStatuses::for_stages(&task.stages);
        task
    }

    #[test]
    fn stages_must_form_a_prefix() {
        assert!(BatchStages { media: false, reconstruction: false, training: false }.validate_prefix().is_err());
        assert!(BatchStages { media: false, reconstruction: true, training: false }.validate_prefix().is_err());
        assert!(BatchStages { media: true, reconstruction: false, training: true }.validate_prefix().is_err());
        assert!(BatchStages { media: true, reconstruction: true, training: true }.validate_prefix().is_ok());
    }

    #[test]
    fn task_must_still_point_to_the_configured_project_revision() {
        let project: crate::contracts::XpanoProjectV2 = serde_json::from_str(include_str!(
            "../../../schemas/fixtures/xpano_project_v3.example.json"
        ))
        .unwrap();
        let mut item = task(BatchStages { media: true, reconstruction: false, training: false });
        item.project_id = project.project_id.clone();
        item.configured_revision = project.revision;
        assert!(validate_task_project(&item, &project).is_ok());

        item.project_id = "another-project".to_string();
        assert_eq!(validate_task_project(&item, &project).unwrap_err().code, "invalid_project");
        item.project_id = project.project_id.clone();
        item.configured_revision += 1;
        assert_eq!(validate_task_project(&item, &project).unwrap_err().code, "revision_conflict");
    }

    #[test]
    fn enqueue_resets_previous_failure_without_reusing_progress() {
        let mut queue = BatchQueueFile::empty();
        let mut item = task(BatchStages { media: true, reconstruction: true, training: false });
        item.state = BatchTaskState::Failed;
        item.last_error = Some(BatchError { code: "x".to_string(), stage: Some("media".to_string()), message: "bad".to_string() });
        item.progress.percent = 78.0;
        item.stage_job_ids.insert("media".to_string(), serde_json::json!("old-job"));
        item.started_at = Some(now_iso());
        item.finished_at = Some(now_iso());
        queue.tasks.push(item.clone());
        queue.enqueue(&item.task_id).unwrap();
        let queued = &queue.tasks[0];
        assert_eq!(queued.state, BatchTaskState::Queued);
        assert_eq!(queued.progress.percent, 0.0);
        assert!(queued.last_error.is_none());
        assert_eq!(queued.stage_status.media, BatchStageStatus::Pending);
        assert!(queued.stage_job_ids.is_empty());
        assert!(queued.started_at.is_none());
        assert!(queued.finished_at.is_none());
    }

    #[test]
    fn first_saved_task_starts_at_order_zero() {
        let mut queue = BatchQueueFile::empty();
        let saved = queue.upsert(task(BatchStages { media: true, reconstruction: false, training: false })).unwrap();
        assert_eq!(saved.order, 0);
    }

    #[test]
    fn running_task_cannot_be_removed_or_reordered() {
        let mut queue = BatchQueueFile::empty();
        let mut one = task(BatchStages { media: true, reconstruction: false, training: false });
        one.state = BatchTaskState::Running;
        queue.tasks.push(one.clone());
        assert!(queue.remove(&one.task_id).is_err());
        assert!(queue.reorder(&[one.task_id]).is_err());
    }

    #[test]
    fn queued_task_inputs_cannot_be_edited_or_removed() {
        let mut queue = BatchQueueFile::empty();
        let mut queued = task(BatchStages { media: true, reconstruction: true, training: false });
        queued.state = BatchTaskState::Queued;
        queue.tasks.push(queued.clone());

        let mut edited = queued.clone();
        edited.label = "Changed".to_string();
        assert!(queue.upsert(edited).is_err());
        assert!(queue.remove(&queued.task_id).is_err());
    }

    #[test]
    fn finishing_one_task_keeps_queue_running_when_more_tasks_are_queued() {
        let mut queue = BatchQueueFile::empty();
        let mut first = task(BatchStages { media: true, reconstruction: false, training: false });
        let mut second = task(BatchStages { media: true, reconstruction: false, training: false });
        second.state = BatchTaskState::Queued;
        second.order = 1;
        first.state = BatchTaskState::Queued;
        let first_id = first.task_id.clone();
        queue.tasks.push(first);
        queue.tasks.push(second);
        queue.mark_task_running(&first_id, "media").unwrap();
        queue.mark_task_finished(&first_id, BatchTaskState::Failed, Some(BatchError { code: "stage_failed".to_string(), stage: Some("media".to_string()), message: "failed".to_string() })).unwrap();
        assert_eq!(queue.state, BatchQueueState::Running);
        assert_eq!(queue.tasks[0].stage_status.media, BatchStageStatus::Failed);
        assert!(queue.tasks.iter().any(|item| item.state == BatchTaskState::Queued));
    }

    #[test]
    fn application_shutdown_interrupts_only_the_active_task() {
        let mut queue = BatchQueueFile::empty();
        let mut active = task(BatchStages { media: true, reconstruction: true, training: false });
        let mut pending = task(BatchStages { media: true, reconstruction: false, training: false });
        active.state = BatchTaskState::Queued;
        pending.state = BatchTaskState::Queued;
        pending.order = 1;
        let active_id = active.task_id.clone();
        queue.tasks.extend([active, pending]);
        queue.mark_task_running(&active_id, "media").unwrap();

        queue.interrupt_active_for_shutdown().unwrap();

        assert_eq!(queue.state, BatchQueueState::Idle);
        assert_eq!(queue.active_task_id, None);
        assert_eq!(queue.tasks[0].state, BatchTaskState::Interrupted);
        assert_eq!(queue.tasks[1].state, BatchTaskState::Queued);
    }

    #[test]
    fn completed_stage_percent_reaches_one_hundred_for_shorter_pipelines() {
        let media_only = task(BatchStages { media: true, reconstruction: false, training: false });
        assert_eq!(completed_stage_percent(&media_only, "media"), 100.0);

        let through_reconstruction = task(BatchStages { media: true, reconstruction: true, training: false });
        assert_eq!(completed_stage_percent(&through_reconstruction, "media"), 50.0);
        assert_eq!(completed_stage_percent(&through_reconstruction, "reconstruction"), 100.0);

        let full = task(BatchStages { media: true, reconstruction: true, training: true });
        assert_eq!(completed_stage_percent(&full, "training"), 100.0);
    }

    #[test]
    fn batch_reconstruction_uses_every_persisted_metashape_setting() {
        let root = std::env::temp_dir().join(format!("xpano-batch-args-{}", Uuid::new_v4()));
        let mut project: crate::contracts::XpanoProjectV2 = serde_json::from_str(include_str!(
            "../../../schemas/fixtures/xpano_project_v3.example.json"
        ))
        .unwrap();
        project.reconstruction.backend = crate::contracts::ReconstructionBackend::Metashape;
        project.reconstruction.config = serde_json::json!({
            "mediaManifestPath": "manifests/media.json",
            "metashapePath": "C:/Program Files/Agisoft/Metashape/metashape.exe",
            "alignmentMode": "backbone",
            "metashapeKeypointLimit": 32000,
            "metashapeTiepointLimit": 6000,
            "upAxis": "+Z"
        });
        crate::project::write_project_atomic(&root, &project).unwrap();

        let args = default_reconstruction_args(&root).unwrap();
        assert!(args.windows(2).any(|pair| pair == ["--output", root.to_string_lossy().as_ref()]));
        assert!(args.windows(2).any(|pair| pair == ["--metashape-alignment-mode", "backbone"]));
        assert!(args.windows(2).any(|pair| pair == ["--metashape-keypoint-limit", "32000"]));
        assert!(args.windows(2).any(|pair| pair == ["--metashape-tiepoint-limit", "6000"]));
        assert!(args.windows(2).any(|pair| pair == ["--up-axis", "+Z"]));
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn batch_reconstruction_uses_every_persisted_colmap_setting() {
        let root = std::env::temp_dir().join(format!("xpano-batch-colmap-args-{}", Uuid::new_v4()));
        let mut project: crate::contracts::XpanoProjectV2 = serde_json::from_str(include_str!(
            "../../../schemas/fixtures/xpano_project_v3.example.json"
        ))
        .unwrap();
        project.reconstruction.backend = crate::contracts::ReconstructionBackend::Colmap;
        project.reconstruction.config = serde_json::json!({
            "mediaManifestPath": "manifests/media.json",
            "colmapDensityPreset": "high-density",
            "colmapUseGpu": true,
            "colmapMatcher": "exhaustive",
            "colmapMaxImageSize": 2048,
            "colmapMaxNumFeatures": 8192,
            "upAxis": "+Y"
        });
        crate::project::write_project_atomic(&root, &project).unwrap();

        let args = default_reconstruction_args(&root).unwrap();
        assert!(args.windows(2).any(|pair| pair == ["--backend", "colmap"]));
        assert!(args.windows(2).any(|pair| pair == ["--colmap-density-preset", "high-density"]));
        assert!(args.windows(2).any(|pair| pair == ["--colmap-matcher", "exhaustive"]));
        assert!(args.iter().any(|value| value == "--colmap-use-gpu"));
        assert!(args.windows(2).any(|pair| pair == ["--colmap-max-image-size", "2048"]));
        assert!(args.windows(2).any(|pair| pair == ["--colmap-max-num-features", "8192"]));
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn corrupt_queue_keeps_the_original_and_creates_a_backup() {
        let root = std::env::temp_dir().join(format!("xpano-batch-corrupt-{}", Uuid::new_v4()));
        std::fs::create_dir_all(&root).unwrap();
        let path = root.join("queue.json");
        std::fs::write(&path, b"{ definitely not json").unwrap();

        assert!(load_queue(&path).is_err());
        assert!(path.is_file());
        assert!(std::fs::read_dir(&root).unwrap().flatten().any(|entry| {
            entry.file_name().to_string_lossy().starts_with("queue.json.corrupt.")
        }));
        let _ = std::fs::remove_dir_all(root);
    }
}
