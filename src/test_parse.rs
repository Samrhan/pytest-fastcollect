// Test file parsing directly
use rustpython_parser::{ast, Parse};
use std::fs;

fn main() {
    let test_file = "tests/sample_tests/test_basic.py";
    let content = fs::read_to_string(test_file).expect("Failed to read file");

    println!("File content length: {}", content.len());
    println!("First 100 chars: {}", &content[..100.min(content.len())]);

    match ast::Suite::parse(&content, test_file) {
        Ok(module) => {
            println!("Parsed successfully!");
            println!("Number of statements: {}", module.len());

            for (i, stmt) in module.iter().enumerate() {
                match stmt {
                    ast::Stmt::FunctionDef(func) => {
                        println!("  [{}] Function: {}", i, func.name.as_str());
                    }
                    ast::Stmt::ClassDef(class) => {
                        println!("  [{}] Class: {}", i, class.name.as_str());
                    }
                    _ => {
                        println!("  [{}] Other: {:?}", i, stmt);
                    }
                }
            }
        }
        Err(e) => {
            println!("Parse error: {:?}", e);
        }
    }
}
