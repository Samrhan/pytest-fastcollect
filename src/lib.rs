use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use rayon::prelude::*;
use rustpython_parser::{ast, Parse};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::RwLock;
use std::time::SystemTime;
use walkdir::WalkDir;

// PHASE 3: Rust-side caching constants
const CACHE_VERSION: &str = "1.0";
const MTIME_TOLERANCE_SECONDS: f64 = 0.01;

#[derive(Debug, Clone, Serialize, Deserialize)]
struct TestItem {
    file_path: String,
    name: String,
    line_number: usize,
    item_type: TestItemType,
    class_name: Option<String>,
    markers: Vec<String>,
    /// Parametrize info: list of parameter sets (for generating correct number of test nodes)
    parametrize_count: Option<usize>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
enum TestItemType {
    Function,
    Class,
    Method,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct FileMetadata {
    path: String,
    mtime: f64,
    test_items: Vec<TestItem>,
}

/// PHASE 3: Cache entry for storing parsed test data with modification time
#[derive(Debug, Clone, Serialize, Deserialize)]
struct CacheEntry {
    mtime: f64,
    items: Vec<TestItem>,
}

/// PHASE 3: Cache structure for persistence
#[derive(Debug, Clone, Serialize, Deserialize)]
struct CacheData {
    version: String,
    entries: HashMap<String, CacheEntry>,
}

/// Test filter for keyword and marker expressions
#[derive(Debug, Clone)]
struct TestFilter {
    keyword_expr: Option<String>,
    marker_expr: Option<String>,
}

impl TestFilter {
    fn new(keyword_expr: Option<String>, marker_expr: Option<String>) -> Self {
        TestFilter {
            keyword_expr,
            marker_expr,
        }
    }

    /// Check if a test item matches the filter criteria
    fn matches(&self, item: &TestItem) -> bool {
        // If no filters, everything matches
        if self.keyword_expr.is_none() && self.marker_expr.is_none() {
            return true;
        }

        // Check keyword filter
        if let Some(ref expr) = self.keyword_expr {
            if !self.matches_keyword(item, expr) {
                return false;
            }
        }

        // Check marker filter
        if let Some(ref expr) = self.marker_expr {
            if !self.matches_marker(item, expr) {
                return false;
            }
        }

        true
    }

    /// Check if test matches keyword expression (-k)
    fn matches_keyword(&self, item: &TestItem, expr: &str) -> bool {
        // Build searchable text from test item
        let mut parts = vec![item.name.to_lowercase()];

        if let Some(ref class_name) = item.class_name {
            parts.push(class_name.to_lowercase());
        }

        // Add filename without extension
        if let Some(filename) = Path::new(&item.file_path).file_stem() {
            parts.push(filename.to_string_lossy().to_lowercase());
        }

        let search_text = parts.join(" ");

        self.evaluate_expression(expr, &search_text)
    }

    /// Check if test matches marker expression (-m)
    fn matches_marker(&self, item: &TestItem, expr: &str) -> bool {
        let marker_set: HashSet<String> = item
            .markers
            .iter()
            .map(|m| m.to_lowercase())
            .collect();

        self.evaluate_marker_expression(expr, &marker_set)
    }

    /// Evaluate keyword expression against search text
    fn evaluate_expression(&self, expr: &str, search_text: &str) -> bool {
        let expr = expr.to_lowercase().trim().to_string();

        // Handle simple case: single keyword
        if !expr.contains(" and ") && !expr.contains(" or ") && !expr.starts_with("not ") {
            return search_text.contains(&expr);
        }

        // Handle NOT
        if expr.starts_with("not ") {
            let keyword = expr[4..].trim();
            return !search_text.contains(keyword);
        }

        // Handle AND (has higher precedence than OR in pytest)
        if expr.contains(" and ") {
            let parts: Vec<&str> = expr.split(" and ").collect();
            return parts
                .iter()
                .all(|p| self.evaluate_expression(p.trim(), search_text));
        }

        // Handle OR
        if expr.contains(" or ") {
            let parts: Vec<&str> = expr.split(" or ").collect();
            return parts
                .iter()
                .any(|p| self.evaluate_expression(p.trim(), search_text));
        }

        search_text.contains(&expr)
    }

    /// Evaluate marker expression against marker set
    fn evaluate_marker_expression(&self, expr: &str, markers: &HashSet<String>) -> bool {
        let expr = expr.to_lowercase().trim().to_string();

        // Handle simple case: single marker
        if !expr.contains(" and ") && !expr.contains(" or ") && !expr.starts_with("not ") {
            return markers.contains(&expr);
        }

        // Handle NOT
        if expr.starts_with("not ") {
            let marker = expr[4..].trim();
            return !markers.contains(marker);
        }

        // Handle AND
        if expr.contains(" and ") {
            let parts: Vec<&str> = expr.split(" and ").collect();
            return parts
                .iter()
                .all(|p| self.evaluate_marker_expression(p.trim(), markers));
        }

        // Handle OR
        if expr.contains(" or ") {
            let parts: Vec<&str> = expr.split(" or ").collect();
            return parts
                .iter()
                .any(|p| self.evaluate_marker_expression(p.trim(), markers));
        }

        markers.contains(&expr)
    }
}

/// Fast test collector using Rust
#[pyclass]
struct FastCollector {
    root_path: PathBuf,
    test_patterns: Vec<String>,
    ignore_patterns: Vec<String>,
    // PHASE 3: Rust-side caching to eliminate FFI overhead
    // Using RwLock for thread-safe interior mutability (works with Rayon parallel iterators)
    cache_path: RwLock<Option<PathBuf>>,
    cache: RwLock<HashMap<String, CacheEntry>>,
}

#[pymethods]
impl FastCollector {
    #[new]
    fn new(root_path: String) -> Self {
        FastCollector {
            root_path: PathBuf::from(root_path),
            test_patterns: vec![
                "test_*.py".to_string(),
                "*_test.py".to_string(),
            ],
            ignore_patterns: vec![
                ".git".to_string(),
                "__pycache__".to_string(),
                ".tox".to_string(),
                ".venv".to_string(),
                "venv".to_string(),
                ".eggs".to_string(),
                "*.egg-info".to_string(),
            ],
            // PHASE 3: Initialize cache (empty until cache_path is set)
            cache_path: RwLock::new(None),
            cache: RwLock::new(HashMap::new()),
        }
    }

    /// PHASE 3: Set cache path and load existing cache
    fn set_cache_path(&self, cache_path: String) -> PyResult<()> {
        let path = PathBuf::from(cache_path);
        *self.cache_path.write().unwrap() = Some(path);
        self.load_cache();
        Ok(())
    }

    /// Collect all test files and parse them for test items
    fn collect(&self, py: Python) -> PyResult<Py<PyAny>> {
        let test_files = self.find_test_files();

        // Use rayon for parallel processing
        let all_items: Vec<TestItem> = test_files
            .par_iter()
            .flat_map(|file_path| {
                self.parse_test_file(file_path).unwrap_or_default()
            })
            .collect();

        // Convert to Python dict
        self.items_to_python(py, &all_items)
    }

    /// Collect with file metadata (includes modification times)
    fn collect_with_metadata(&self, py: Python) -> PyResult<Py<PyAny>> {
        let test_files = self.find_test_files();

        // Use rayon for parallel processing
        let file_metadata: Vec<FileMetadata> = test_files
            .par_iter()
            .filter_map(|file_path| {
                // Get file modification time
                let mtime = match fs::metadata(file_path) {
                    Ok(metadata) => {
                        match metadata.modified() {
                            Ok(time) => {
                                match time.duration_since(SystemTime::UNIX_EPOCH) {
                                    Ok(duration) => duration.as_secs_f64(),
                                    Err(_) => 0.0,
                                }
                            }
                            Err(_) => 0.0,
                        }
                    }
                    Err(_) => 0.0,
                };

                // Parse test items
                let test_items = self.parse_test_file(file_path).unwrap_or_default();

                if test_items.is_empty() {
                    return None;
                }

                Some(FileMetadata {
                    path: file_path.to_string_lossy().to_string(),
                    mtime,
                    test_items,
                })
            })
            .collect();

        // Convert to Python dict
        self.metadata_to_python(py, &file_metadata)
    }

    /// Collect tests from a specific file
    fn collect_file(&self, py: Python, file_path: String) -> PyResult<Py<PyAny>> {
        let path = PathBuf::from(file_path);
        let items = self.parse_test_file(&path).unwrap_or_default();
        self.items_to_python(py, &items)
    }

    /// Collect all test files and return metadata as JSON string
    /// This is MUCH faster than building PyDict/PyList objects across FFI boundary
    fn collect_json(&self) -> PyResult<String> {
        let test_files = self.find_test_files();

        // Use rayon for parallel processing
        let file_metadata: Vec<FileMetadata> = test_files
            .par_iter()
            .filter_map(|file_path| {
                // Get file modification time
                let mtime = match fs::metadata(file_path) {
                    Ok(metadata) => {
                        match metadata.modified() {
                            Ok(time) => {
                                match time.duration_since(SystemTime::UNIX_EPOCH) {
                                    Ok(duration) => duration.as_secs_f64(),
                                    Err(_) => 0.0,
                                }
                            }
                            Err(_) => 0.0,
                        }
                    }
                    Err(_) => 0.0,
                };

                // Parse test items
                let test_items = self.parse_test_file(file_path).unwrap_or_default();

                if test_items.is_empty() {
                    return None;
                }

                Some(FileMetadata {
                    path: file_path.to_string_lossy().to_string(),
                    mtime,
                    test_items,
                })
            })
            .collect();

        // Serialize to JSON in one go - much faster than thousands of FFI calls!
        serde_json::to_string(&file_metadata)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("JSON serialization failed: {}", e)))
    }

    /// Collect with filtering applied in Rust (MUCH faster than Python filtering)
    /// This is the "quick win" optimization - filters tests during Rayon parallel iteration
    #[pyo3(signature = (keyword_expr=None, marker_expr=None))]
    fn collect_json_filtered(
        &self,
        keyword_expr: Option<String>,
        marker_expr: Option<String>,
    ) -> PyResult<String> {
        let test_files = self.find_test_files();
        let filter = TestFilter::new(keyword_expr, marker_expr);

        // PHASE 3: Use cache to avoid re-parsing unchanged files
        // Use rayon for parallel processing WITH caching AND filtering
        let file_metadata: Vec<FileMetadata> = test_files
            .par_iter()
            .filter_map(|file_path| {
                let file_path_str = file_path.to_string_lossy().to_string();

                // Get file modification time
                let mtime = match fs::metadata(file_path) {
                    Ok(metadata) => {
                        match metadata.modified() {
                            Ok(time) => {
                                match time.duration_since(SystemTime::UNIX_EPOCH) {
                                    Ok(duration) => duration.as_secs_f64(),
                                    Err(_) => 0.0,
                                }
                            }
                            Err(_) => 0.0,
                        }
                    }
                    Err(_) => 0.0,
                };

                // PHASE 3: Try to get items from cache first
                let all_items = if let Some(cached_items) = self.get_cached_items(&file_path_str, mtime) {
                    // Cache hit! Use cached items (avoids AST parsing)
                    cached_items
                } else {
                    // Cache miss - parse file and update cache
                    let parsed_items = self.parse_test_file(file_path).unwrap_or_default();
                    self.update_cache(file_path_str.clone(), mtime, parsed_items.clone());
                    parsed_items
                };

                // CRITICAL: Apply filter HERE in Rust, not in Python!
                // This avoids creating Python objects for filtered-out tests
                let test_items: Vec<TestItem> = all_items
                    .into_iter()
                    .filter(|item| filter.matches(item))
                    .collect();

                // Skip file if no matching tests
                if test_items.is_empty() {
                    return None;
                }

                Some(FileMetadata {
                    path: file_path_str,
                    mtime,
                    test_items,
                })
            })
            .collect();

        // PHASE 3: Save cache after collection (non-fatal if it fails)
        let _ = self.save_cache();

        // Serialize to JSON
        serde_json::to_string(&file_metadata)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("JSON serialization failed: {}", e)))
    }
}

impl FastCollector {
    /// PHASE 3: Load cache from disk
    fn load_cache(&self) {
        let cache_path_opt = self.cache_path.read().unwrap().clone();
        if let Some(cache_path) = cache_path_opt {
            if cache_path.exists() {
                match fs::read_to_string(&cache_path) {
                    Ok(contents) => {
                        match serde_json::from_str::<CacheData>(&contents) {
                            Ok(cache_data) => {
                                // Check version
                                if cache_data.version == CACHE_VERSION {
                                    *self.cache.write().unwrap() = cache_data.entries;
                                } else {
                                    // Version mismatch, start fresh
                                    self.cache.write().unwrap().clear();
                                }
                            }
                            Err(_) => {
                                // Corrupted cache, start fresh
                                self.cache.write().unwrap().clear();
                            }
                        }
                    }
                    Err(_) => {
                        // Can't read cache, start fresh
                        self.cache.write().unwrap().clear();
                    }
                }
            }
        }
    }

    /// PHASE 3: Save cache to disk
    fn save_cache(&self) -> Result<(), Box<dyn std::error::Error>> {
        let cache_path_opt = self.cache_path.read().unwrap().clone();
        if let Some(cache_path) = cache_path_opt {
            // Ensure parent directory exists
            if let Some(parent) = cache_path.parent() {
                fs::create_dir_all(parent)?;
            }

            let cache_data = CacheData {
                version: CACHE_VERSION.to_string(),
                entries: self.cache.read().unwrap().clone(),
            };

            let json = serde_json::to_string_pretty(&cache_data)?;
            fs::write(cache_path, json)?;
        }
        Ok(())
    }

    /// PHASE 3: Get cached data for a file if it's still valid
    fn get_cached_items(&self, file_path: &str, current_mtime: f64) -> Option<Vec<TestItem>> {
        let cache = self.cache.read().unwrap();
        if let Some(entry) = cache.get(file_path) {
            // Check if mtime matches (within tolerance)
            if (entry.mtime - current_mtime).abs() < MTIME_TOLERANCE_SECONDS {
                return Some(entry.items.clone());
            }
        }
        None
    }

    /// PHASE 3: Update cache with newly parsed data
    fn update_cache(&self, file_path: String, mtime: f64, items: Vec<TestItem>) {
        self.cache.write().unwrap().insert(file_path, CacheEntry { mtime, items });
    }

    /// Find all test files in the directory tree
    fn find_test_files(&self) -> Vec<PathBuf> {
        WalkDir::new(&self.root_path)
            .into_iter()
            .filter_entry(|e| {
                // Skip ignored directories
                !self.should_ignore(e.path())
            })
            .filter_map(|e| e.ok())
            .filter(|e| e.file_type().is_file())
            .filter(|e| self.is_test_file(e.path()))
            .map(|e| e.path().to_path_buf())
            .collect()
    }

    /// Check if a path should be ignored
    fn should_ignore(&self, path: &Path) -> bool {
        if let Some(name) = path.file_name() {
            let name_str = name.to_string_lossy();
            for pattern in &self.ignore_patterns {
                if pattern.contains('*') {
                    // Simple wildcard matching
                    if self.matches_wildcard(&name_str, pattern) {
                        return true;
                    }
                } else if name_str == pattern.as_str() {
                    return true;
                }
            }
        }
        false
    }

    /// Simple wildcard matching (supports * anywhere in pattern)
    fn matches_wildcard(&self, text: &str, pattern: &str) -> bool {
        // Split pattern by '*'
        let parts: Vec<&str> = pattern.split('*').collect();

        if parts.len() == 1 {
            // No wildcards, exact match
            return text == pattern;
        }

        let mut current_pos = 0;

        for (i, part) in parts.iter().enumerate() {
            if part.is_empty() {
                continue;
            }

            if i == 0 {
                // First part must match at start
                if !text.starts_with(part) {
                    return false;
                }
                current_pos = part.len();
            } else if i == parts.len() - 1 {
                // Last part must match at end
                if !text.ends_with(part) {
                    return false;
                }
                // Check that we haven't gone past the end
                if current_pos > text.len() - part.len() {
                    return false;
                }
            } else {
                // Middle parts can match anywhere after current position
                if let Some(pos) = text[current_pos..].find(part) {
                    current_pos += pos + part.len();
                } else {
                    return false;
                }
            }
        }

        true
    }

    /// Check if a file is a test file based on naming patterns
    fn is_test_file(&self, path: &Path) -> bool {
        if let Some(name) = path.file_name() {
            let name_str = name.to_string_lossy();
            if !name_str.ends_with(".py") {
                return false;
            }
            for pattern in &self.test_patterns {
                if self.matches_wildcard(&name_str, pattern) {
                    return true;
                }
            }
        }
        false
    }

    /// Parse a test file and extract test items
    fn parse_test_file(&self, path: &Path) -> Result<Vec<TestItem>, Box<dyn std::error::Error>> {
        let content = fs::read_to_string(path)?;
        let file_path = path.to_string_lossy().to_string();

        let module = match ast::Suite::parse(&content, &file_path) {
            Ok(m) => m,
            Err(_) => return Ok(Vec::new()), // Skip files with parse errors
        };

        let mut items = Vec::new();

        for stmt in &module {
            self.extract_test_items(stmt, &file_path, None, &mut items);
        }

        Ok(items)
    }

    /// Extract test items from AST nodes
    fn extract_test_items(
        &self,
        stmt: &ast::Stmt,
        file_path: &str,
        class_context: Option<&str>,
        items: &mut Vec<TestItem>,
    ) {
        match stmt {
            ast::Stmt::FunctionDef(func) => {
                let name = func.name.as_str();
                if self.is_test_function(name) {
                    let markers = self.extract_markers(&func.decorator_list);
                    let parametrize_count = self.extract_parametrize_count(&func.decorator_list);
                    items.push(TestItem {
                        file_path: file_path.to_string(),
                        name: name.to_string(),
                        line_number: func.range.start().to_u32() as usize,
                        item_type: if class_context.is_some() {
                            TestItemType::Method
                        } else {
                            TestItemType::Function
                        },
                        class_name: class_context.map(|s| s.to_string()),
                        markers,
                        parametrize_count,
                    });
                }
            }
            ast::Stmt::ClassDef(class) => {
                let class_name = class.name.as_str();
                if self.is_test_class(class_name) {
                    let markers = self.extract_markers(&class.decorator_list);
                    // Add the class itself
                    items.push(TestItem {
                        file_path: file_path.to_string(),
                        name: class_name.to_string(),
                        line_number: class.range.start().to_u32() as usize,
                        item_type: TestItemType::Class,
                        class_name: None,
                        markers,
                        parametrize_count: None,
                    });

                    // Extract methods from the class
                    for stmt in &class.body {
                        self.extract_test_items(stmt, file_path, Some(class_name), items);
                    }
                }
            }
            _ => {}
        }
    }

    /// Extract pytest markers from decorator list
    fn extract_markers(&self, decorators: &[ast::Expr]) -> Vec<String> {
        let mut markers = Vec::new();

        for decorator in decorators {
            // Handle @pytest.mark.marker_name or @mark.marker_name
            if let ast::Expr::Attribute(attr) = decorator {
                if let ast::Expr::Attribute(parent_attr) = attr.value.as_ref() {
                    if let ast::Expr::Name(name) = parent_attr.value.as_ref() {
                        if name.id.as_str() == "pytest" && parent_attr.attr.as_str() == "mark" {
                            markers.push(attr.attr.to_string());
                        }
                    }
                } else if let ast::Expr::Name(name) = attr.value.as_ref() {
                    if name.id.as_str() == "mark" {
                        markers.push(attr.attr.to_string());
                    }
                }
            }
            // Handle @pytest.mark.marker_name(...) or @mark.marker_name(...)
            else if let ast::Expr::Call(call) = decorator {
                if let ast::Expr::Attribute(attr) = call.func.as_ref() {
                    if let ast::Expr::Attribute(parent_attr) = attr.value.as_ref() {
                        if let ast::Expr::Name(name) = parent_attr.value.as_ref() {
                            if name.id.as_str() == "pytest" && parent_attr.attr.as_str() == "mark" {
                                markers.push(attr.attr.to_string());
                            }
                        }
                    } else if let ast::Expr::Name(name) = attr.value.as_ref() {
                        if name.id.as_str() == "mark" {
                            markers.push(attr.attr.to_string());
                        }
                    }
                }
            }
        }

        markers
    }

    /// Extract parametrize count from decorator list
    /// Parses @pytest.mark.parametrize("arg", [val1, val2, ...]) to count parameter sets
    /// This allows us to generate the correct number of test nodes WITHOUT importing Python code!
    fn extract_parametrize_count(&self, decorators: &[ast::Expr]) -> Option<usize> {
        for decorator in decorators {
            // Look for @pytest.mark.parametrize(...) or @mark.parametrize(...)
            if let ast::Expr::Call(call) = decorator {
                if let ast::Expr::Attribute(attr) = call.func.as_ref() {
                    let is_parametrize = attr.attr.as_str() == "parametrize";

                    if !is_parametrize {
                        continue;
                    }

                    // Check if it's pytest.mark.parametrize or mark.parametrize
                    let is_pytest_mark = if let ast::Expr::Attribute(parent_attr) = attr.value.as_ref() {
                        if let ast::Expr::Name(name) = parent_attr.value.as_ref() {
                            name.id.as_str() == "pytest" && parent_attr.attr.as_str() == "mark"
                        } else {
                            false
                        }
                    } else if let ast::Expr::Name(name) = attr.value.as_ref() {
                        name.id.as_str() == "mark"
                    } else {
                        false
                    };

                    if !is_pytest_mark {
                        continue;
                    }

                    // Try to extract the parameter count from the second argument
                    // @pytest.mark.parametrize("arg", [val1, val2, val3]) -> count = 3
                    // @pytest.mark.parametrize("arg1,arg2", [(v1,v2), (v3,v4)]) -> count = 2
                    if call.args.len() >= 2 {
                        if let ast::Expr::List(list_expr) = &call.args[1] {
                            return Some(list_expr.elts.len());
                        } else if let ast::Expr::Tuple(tuple_expr) = &call.args[1] {
                            return Some(tuple_expr.elts.len());
                        }
                    }
                }
            }
        }

        None
    }

    /// Check if a function name indicates a test function
    fn is_test_function(&self, name: &str) -> bool {
        name.starts_with("test_") || name.starts_with("test")
    }

    /// Check if a class name indicates a test class
    fn is_test_class(&self, name: &str) -> bool {
        name.starts_with("Test")
    }

    /// Convert test items to Python dict structure with rich metadata
    fn items_to_python(&self, py: Python, items: &[TestItem]) -> PyResult<Py<PyAny>> {
        let result = PyDict::new(py);

        // Group by file
        let mut files_map: HashMap<String, Vec<&TestItem>> = HashMap::new();
        for item in items {
            files_map.entry(item.file_path.clone())
                .or_insert_with(Vec::new)
                .push(item);
        }

        for (file_path, file_items) in files_map {
            let items_list = PyList::empty(py);

            for item in file_items {
                let item_dict = PyDict::new(py);
                item_dict.set_item("name", &item.name)?;
                item_dict.set_item("line", item.line_number)?;
                item_dict.set_item("type", format!("{:?}", item.item_type))?;
                item_dict.set_item("file_path", &item.file_path)?;

                if let Some(ref class_name) = item.class_name {
                    item_dict.set_item("class", class_name)?;
                }

                // Add markers
                let markers_list = PyList::empty(py);
                for marker in &item.markers {
                    markers_list.append(marker)?;
                }
                item_dict.set_item("markers", markers_list)?;

                // Add parametrize count
                if let Some(count) = item.parametrize_count {
                    item_dict.set_item("parametrize_count", count)?;
                }

                items_list.append(item_dict)?;
            }

            result.set_item(file_path, items_list)?;
        }

        Ok(result.into())
    }

    /// Convert file metadata to Python dict structure
    fn metadata_to_python(&self, py: Python, metadata: &[FileMetadata]) -> PyResult<Py<PyAny>> {
        let result = PyDict::new(py);

        for file_meta in metadata {
            let file_dict = PyDict::new(py);
            file_dict.set_item("mtime", file_meta.mtime)?;

            let items_list = PyList::empty(py);
            for item in &file_meta.test_items {
                let item_dict = PyDict::new(py);
                item_dict.set_item("name", &item.name)?;
                item_dict.set_item("line", item.line_number)?;
                item_dict.set_item("type", format!("{:?}", item.item_type))?;
                item_dict.set_item("file_path", &item.file_path)?;

                if let Some(ref class_name) = item.class_name {
                    item_dict.set_item("class", class_name)?;
                }

                // Add markers
                let markers_list = PyList::empty(py);
                for marker in &item.markers {
                    markers_list.append(marker)?;
                }
                item_dict.set_item("markers", markers_list)?;

                // Add parametrize count
                if let Some(count) = item.parametrize_count {
                    item_dict.set_item("parametrize_count", count)?;
                }

                items_list.append(item_dict)?;
            }
            file_dict.set_item("items", items_list)?;

            result.set_item(&file_meta.path, file_dict)?;
        }

        Ok(result.into())
    }
}

/// A Python module implemented in Rust.
#[pymodule]
fn pytest_fastcollect(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<FastCollector>()?;
    m.add_function(wrap_pyfunction!(get_version, m)?)?;
    Ok(())
}

/// Get version information
#[pyfunction]
fn get_version() -> PyResult<String> {
    Ok(env!("CARGO_PKG_VERSION").to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::io::Write;
    use tempfile::TempDir;

    /// Helper function to create a temporary test file
    fn create_test_file(dir: &TempDir, name: &str, content: &str) -> PathBuf {
        let file_path = dir.path().join(name);
        let mut file = fs::File::create(&file_path).unwrap();
        file.write_all(content.as_bytes()).unwrap();
        file_path
    }

    #[test]
    fn test_is_test_function_with_test_prefix() {
        let collector = FastCollector::new("/tmp".to_string());
        assert!(collector.is_test_function("test_foo"));
        assert!(collector.is_test_function("test_bar_baz"));
        assert!(collector.is_test_function("test"));
    }

    #[test]
    fn test_is_test_function_without_test_prefix() {
        let collector = FastCollector::new("/tmp".to_string());
        assert!(!collector.is_test_function("foo_test"));
        assert!(!collector.is_test_function("my_function"));
        assert!(!collector.is_test_function("Test"));
    }

    #[test]
    fn test_is_test_class_with_test_prefix() {
        let collector = FastCollector::new("/tmp".to_string());
        assert!(collector.is_test_class("TestFoo"));
        assert!(collector.is_test_class("TestBarBaz"));
        assert!(collector.is_test_class("Test"));
    }

    #[test]
    fn test_is_test_class_without_test_prefix() {
        let collector = FastCollector::new("/tmp".to_string());
        assert!(!collector.is_test_class("FooTest"));
        assert!(!collector.is_test_class("MyClass"));
        assert!(!collector.is_test_class("test_foo"));
    }

    #[test]
    fn test_is_test_file_with_valid_patterns() {
        let collector = FastCollector::new("/tmp".to_string());
        let test_file = PathBuf::from("test_foo.py");
        let test_file2 = PathBuf::from("bar_test.py");

        assert!(collector.is_test_file(&test_file));
        assert!(collector.is_test_file(&test_file2));
    }

    #[test]
    fn test_is_test_file_with_invalid_patterns() {
        let collector = FastCollector::new("/tmp".to_string());
        let non_test = PathBuf::from("foo.py");
        let non_python = PathBuf::from("test_foo.txt");
        let no_extension = PathBuf::from("test_foo");

        assert!(!collector.is_test_file(&non_test));
        assert!(!collector.is_test_file(&non_python));
        assert!(!collector.is_test_file(&no_extension));
    }

    #[test]
    fn test_should_ignore_common_directories() {
        let collector = FastCollector::new("/tmp".to_string());

        assert!(collector.should_ignore(&PathBuf::from(".git")));
        assert!(collector.should_ignore(&PathBuf::from("__pycache__")));
        assert!(collector.should_ignore(&PathBuf::from(".tox")));
        assert!(collector.should_ignore(&PathBuf::from(".venv")));
        assert!(collector.should_ignore(&PathBuf::from("venv")));
    }

    #[test]
    fn test_should_not_ignore_regular_directories() {
        let collector = FastCollector::new("/tmp".to_string());

        assert!(!collector.should_ignore(&PathBuf::from("tests")));
        assert!(!collector.should_ignore(&PathBuf::from("src")));
        assert!(!collector.should_ignore(&PathBuf::from("my_module")));
    }

    #[test]
    fn test_matches_wildcard_exact_match() {
        let collector = FastCollector::new("/tmp".to_string());

        assert!(collector.matches_wildcard("test.py", "test.py"));
        assert!(!collector.matches_wildcard("test.py", "other.py"));
    }

    #[test]
    fn test_matches_wildcard_prefix() {
        let collector = FastCollector::new("/tmp".to_string());

        assert!(collector.matches_wildcard("test_foo.py", "test_*.py"));
        assert!(collector.matches_wildcard("test_bar_baz.py", "test_*.py"));
        assert!(!collector.matches_wildcard("foo_test.py", "test_*.py"));
    }

    #[test]
    fn test_matches_wildcard_suffix() {
        let collector = FastCollector::new("/tmp".to_string());

        assert!(collector.matches_wildcard("foo_test.py", "*_test.py"));
        assert!(collector.matches_wildcard("bar_baz_test.py", "*_test.py"));
        assert!(!collector.matches_wildcard("test_foo.py", "*_test.py"));
    }

    #[test]
    fn test_matches_wildcard_middle() {
        let collector = FastCollector::new("/tmp".to_string());

        assert!(collector.matches_wildcard("test_foo_bar.py", "test_*_bar.py"));
        assert!(!collector.matches_wildcard("test_foo.py", "test_*_bar.py"));
    }

    #[test]
    fn test_parse_simple_test_function() {
        let temp_dir = TempDir::new().unwrap();
        let collector = FastCollector::new(temp_dir.path().to_str().unwrap().to_string());

        let content = r#"
def test_simple():
    assert True
"#;
        let test_file = create_test_file(&temp_dir, "test_simple.py", content);

        let items = collector.parse_test_file(&test_file).unwrap();
        assert_eq!(items.len(), 1);
        assert_eq!(items[0].name, "test_simple");
        assert_eq!(items[0].class_name, None);
    }

    #[test]
    fn test_parse_test_class() {
        let temp_dir = TempDir::new().unwrap();
        let collector = FastCollector::new(temp_dir.path().to_str().unwrap().to_string());

        let content = r#"
class TestFoo:
    def test_method(self):
        pass
"#;
        let test_file = create_test_file(&temp_dir, "test_class.py", content);

        let items = collector.parse_test_file(&test_file).unwrap();
        // Should have both the class and the method
        assert!(items.len() >= 1);

        // Find the class item
        let class_item = items.iter().find(|i| i.name == "TestFoo");
        assert!(class_item.is_some());

        // Find the method item
        let method_item = items.iter().find(|i| i.name == "test_method");
        assert!(method_item.is_some());
        assert_eq!(method_item.unwrap().class_name, Some("TestFoo".to_string()));
    }

    #[test]
    fn test_parse_with_markers() {
        let temp_dir = TempDir::new().unwrap();
        let collector = FastCollector::new(temp_dir.path().to_str().unwrap().to_string());

        let content = r#"
import pytest

@pytest.mark.slow
def test_slow():
    pass

@pytest.mark.smoke
@pytest.mark.regression
def test_combined():
    pass
"#;
        let test_file = create_test_file(&temp_dir, "test_markers.py", content);

        let items = collector.parse_test_file(&test_file).unwrap();

        // Find slow test
        let slow_test = items.iter().find(|i| i.name == "test_slow").unwrap();
        assert!(slow_test.markers.contains(&"slow".to_string()));

        // Find combined test
        let combined_test = items.iter().find(|i| i.name == "test_combined").unwrap();
        assert!(combined_test.markers.contains(&"smoke".to_string()));
        assert!(combined_test.markers.contains(&"regression".to_string()));
    }

    #[test]
    fn test_parse_empty_file() {
        let temp_dir = TempDir::new().unwrap();
        let collector = FastCollector::new(temp_dir.path().to_str().unwrap().to_string());

        let content = "";
        let test_file = create_test_file(&temp_dir, "test_empty.py", content);

        let items = collector.parse_test_file(&test_file).unwrap();
        assert_eq!(items.len(), 0);
    }

    #[test]
    fn test_parse_non_test_functions() {
        let temp_dir = TempDir::new().unwrap();
        let collector = FastCollector::new(temp_dir.path().to_str().unwrap().to_string());

        let content = r#"
def helper_function():
    pass

def another_helper():
    pass
"#;
        let test_file = create_test_file(&temp_dir, "test_helpers.py", content);

        let items = collector.parse_test_file(&test_file).unwrap();
        assert_eq!(items.len(), 0);
    }

    #[test]
    fn test_parse_invalid_python() {
        let temp_dir = TempDir::new().unwrap();
        let collector = FastCollector::new(temp_dir.path().to_str().unwrap().to_string());

        let content = "this is not valid python syntax !!!";
        let test_file = create_test_file(&temp_dir, "test_invalid.py", content);

        let items = collector.parse_test_file(&test_file).unwrap();
        // Should return empty vec on parse error, not crash
        assert_eq!(items.len(), 0);
    }

    #[test]
    fn test_find_test_files_in_directory() {
        let temp_dir = TempDir::new().unwrap();
        let collector = FastCollector::new(temp_dir.path().to_str().unwrap().to_string());

        // Create test files
        create_test_file(&temp_dir, "test_one.py", "def test_one(): pass");
        create_test_file(&temp_dir, "test_two.py", "def test_two(): pass");
        create_test_file(&temp_dir, "helper.py", "def foo(): pass");

        let test_files = collector.find_test_files();

        assert_eq!(test_files.len(), 2);
        assert!(test_files.iter().any(|p| p.file_name().unwrap() == "test_one.py"));
        assert!(test_files.iter().any(|p| p.file_name().unwrap() == "test_two.py"));
    }

    #[test]
    fn test_find_test_files_ignores_directories() {
        let temp_dir = TempDir::new().unwrap();
        let collector = FastCollector::new(temp_dir.path().to_str().unwrap().to_string());

        // Create test file
        create_test_file(&temp_dir, "test_one.py", "def test_one(): pass");

        // Create ignored directory with test file
        let ignored_dir = temp_dir.path().join("__pycache__");
        fs::create_dir(&ignored_dir).unwrap();
        let mut ignored_file = fs::File::create(ignored_dir.join("test_cached.py")).unwrap();
        ignored_file.write_all(b"def test_cached(): pass").unwrap();

        let test_files = collector.find_test_files();

        // Should only find test_one.py, not test_cached.py
        assert_eq!(test_files.len(), 1);
        assert_eq!(test_files[0].file_name().unwrap(), "test_one.py");
    }

    #[test]
    fn test_extract_markers_pytest_mark() {
        let temp_dir = TempDir::new().unwrap();
        let collector = FastCollector::new(temp_dir.path().to_str().unwrap().to_string());

        let content = r#"
import pytest

@pytest.mark.slow
def test_foo():
    pass
"#;
        let test_file = create_test_file(&temp_dir, "test_markers.py", content);
        let items = collector.parse_test_file(&test_file).unwrap();

        let test_item = items.iter().find(|i| i.name == "test_foo").unwrap();
        assert_eq!(test_item.markers, vec!["slow"]);
    }

    #[test]
    fn test_extract_markers_multiple() {
        let temp_dir = TempDir::new().unwrap();
        let collector = FastCollector::new(temp_dir.path().to_str().unwrap().to_string());

        let content = r#"
import pytest

@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.smoke
def test_foo():
    pass
"#;
        let test_file = create_test_file(&temp_dir, "test_markers.py", content);
        let items = collector.parse_test_file(&test_file).unwrap();

        let test_item = items.iter().find(|i| i.name == "test_foo").unwrap();
        assert!(test_item.markers.contains(&"slow".to_string()));
        assert!(test_item.markers.contains(&"integration".to_string()));
        assert!(test_item.markers.contains(&"smoke".to_string()));
    }

    #[test]
    fn test_line_numbers_are_correct() {
        let temp_dir = TempDir::new().unwrap();
        let collector = FastCollector::new(temp_dir.path().to_str().unwrap().to_string());

        let content = r#"
# Line 1
# Line 2
def test_one():  # Line 3
    pass

# Line 6
def test_two():  # Line 7
    pass
"#;
        let test_file = create_test_file(&temp_dir, "test_lines.py", content);
        let items = collector.parse_test_file(&test_file).unwrap();

        let test_one = items.iter().find(|i| i.name == "test_one").unwrap();
        let test_two = items.iter().find(|i| i.name == "test_two").unwrap();

        // Line numbers start at 0 in the AST, but we report 1-indexed
        assert!(test_one.line_number > 0);
        assert!(test_two.line_number > test_one.line_number);
    }
}
