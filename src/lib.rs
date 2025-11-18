use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use rayon::prelude::*;
use rustpython_parser::{ast, Parse};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::SystemTime;
use walkdir::WalkDir;

#[derive(Debug, Clone)]
struct TestItem {
    file_path: String,
    name: String,
    line_number: usize,
    item_type: TestItemType,
    class_name: Option<String>,
    markers: Vec<String>,
}

#[derive(Debug, Clone)]
enum TestItemType {
    Function,
    Class,
    Method,
}

#[derive(Debug, Clone)]
struct FileMetadata {
    path: String,
    mtime: f64,
    test_items: Vec<TestItem>,
}

/// Fast test collector using Rust
#[pyclass]
struct FastCollector {
    root_path: PathBuf,
    test_patterns: Vec<String>,
    ignore_patterns: Vec<String>,
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
        }
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
}

impl FastCollector {
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
