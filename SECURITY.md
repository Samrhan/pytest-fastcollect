# Security Policy

## Supported Versions

We take security seriously and provide security updates for the following versions:

| Version | Supported          | End of Support |
| ------- | ------------------ | -------------- |
| 0.5.x   | :white_check_mark: | Current        |
| 0.4.x   | :white_check_mark: | 2026-01-01     |
| < 0.4   | :x:                | Ended          |

## Security Features

pytest-fastcollect implements several security measures:

### Input Validation
- Path validation to prevent directory traversal attacks
- Request size limits (10MB max) to prevent DoS
- Command validation for daemon requests
- File type validation (only .py files processed)

### Daemon Security
- Input sanitization for all daemon requests
- Connection limits (max 10 concurrent connections)
- Request timeouts (30s max per request)
- Security checks for file paths (must be within project root)
- No arbitrary code execution from network requests

### Dependency Security
- Minimal runtime dependencies (only pytest>=7.0.0)
- Rust dependencies are statically linked and audited
- No network dependencies or remote code execution

## Reporting a Vulnerability

We take all security vulnerabilities seriously. If you discover a security issue, please report it responsibly:

### 🔒 Private Disclosure (Preferred)

For security vulnerabilities, please **DO NOT** create a public GitHub issue.

Instead, please report security issues privately via:

1. **GitHub Security Advisories** (Recommended)
   - Go to: https://github.com/Samrhan/pytest-fastcollect/security/advisories
   - Click "Report a vulnerability"
   - Provide detailed information about the vulnerability

2. **Email** (Alternative)
   - Send to: security@pytest-fastcollect.dev (if available)
   - Or contact the maintainer directly via their GitHub profile
   - Use PGP encryption if possible (key available in repository)

### What to Include

Please provide the following information in your report:

- **Description**: Clear description of the vulnerability
- **Impact**: Potential impact and severity assessment
- **Reproduction**: Step-by-step instructions to reproduce
- **Environment**: OS, Python version, pytest-fastcollect version
- **POC**: Proof of concept code (if available)
- **Suggested Fix**: Your thoughts on how to fix it (optional)

### Response Timeline

We aim to respond to security reports according to the following timeline:

- **Initial Response**: Within 48 hours
- **Assessment**: Within 7 days
- **Fix Development**: Varies by severity (1-30 days)
- **Release**: Coordinated with reporter
- **Public Disclosure**: After fix is released (typically 7 days)

### Severity Levels

We classify vulnerabilities using the following severity levels:

#### 🔴 Critical (CVSS 9.0-10.0)
- Remote code execution without authentication
- Arbitrary file system access outside project root
- Complete daemon compromise
- **Fix Timeline**: 1-3 days

#### 🟠 High (CVSS 7.0-8.9)
- Privilege escalation
- Denial of service affecting all users
- Information disclosure of sensitive data
- **Fix Timeline**: 7-14 days

#### 🟡 Medium (CVSS 4.0-6.9)
- Denial of service affecting single user
- Limited information disclosure
- Authentication bypass with low impact
- **Fix Timeline**: 14-30 days

#### 🟢 Low (CVSS 0.1-3.9)
- Minor information disclosure
- Issues requiring significant user interaction
- **Fix Timeline**: 30-90 days or next regular release

## Security Best Practices

When using pytest-fastcollect:

### For Users

1. **Keep Updated**: Always use the latest version
   ```bash
   pip install --upgrade pytest-fastcollect
   ```

2. **Daemon Management**: Only run daemon in trusted environments
   - Stop daemon when not in use: `pytest --daemon-stop`
   - Check daemon status regularly: `pytest --daemon-status`
   - Monitor daemon logs for suspicious activity

3. **File Permissions**: Ensure test files have appropriate permissions
   ```bash
   chmod 644 tests/**/*.py  # Read-only for tests
   ```

4. **Network Security**: Daemon uses Unix sockets (local only)
   - No network exposure by default
   - Socket files created with 0600 permissions
   - Each project gets isolated daemon

5. **Dependency Auditing**: Regularly check for vulnerabilities
   ```bash
   pip install safety
   safety check
   ```

### For Contributors

1. **Code Review**: All changes reviewed by maintainers
2. **Static Analysis**: Use bandit for security scanning
   ```bash
   pip install bandit
   bandit -r pytest_fastcollect/
   ```

3. **Dependency Pinning**: Keep dependencies up to date
4. **Input Validation**: Always validate user input
5. **Error Handling**: Never expose sensitive information in errors

## Security Audit History

| Date       | Auditor | Scope                    | Findings | Status   |
|------------|---------|--------------------------|----------|----------|
| 2025-01-15 | Internal| Full codebase review     | 0 Critical, 0 High | Resolved |
| TBD        | External| Professional audit       | Pending  | Planned  |

## Security Tools Used

- **Bandit**: Python security linter
- **Safety**: Dependency vulnerability scanner
- **Cargo Audit**: Rust dependency vulnerability scanner
- **GitHub Dependabot**: Automated dependency updates
- **GitHub CodeQL**: Static analysis (planned)

## Known Security Considerations

### Daemon Process
The collection daemon is a long-running process that imports Python modules. While we implement security measures, be aware:

- **Trusted Code Only**: Only run daemon on code you trust
- **File Permissions**: Daemon respects file system permissions
- **Process Isolation**: Each project gets its own daemon
- **Resource Limits**: Connection and request size limits enforced

### Cache Directory
Cache files are stored in `.pytest_cache/v/fastcollect/`:

- **Content**: Contains parsed test metadata (no sensitive data)
- **Permissions**: Inherits from parent directory
- **Cleanup**: Safe to delete at any time
- **Format**: JSON (human-readable, no code execution)

## Responsible Disclosure Policy

We follow a coordinated disclosure policy:

1. **Report Received**: Acknowledge within 48 hours
2. **Verification**: Confirm and assess within 7 days
3. **Fix Development**: Work with reporter on fix
4. **Testing**: Thorough testing of fix
5. **Release**: Publish patched version
6. **Disclosure**: Public disclosure 7 days after release
7. **Credit**: Reporter credited in CHANGELOG (if desired)

## Security Hall of Fame

We thank the following security researchers for responsible disclosure:

- *Your name could be here! Report vulnerabilities responsibly.*

## Bug Bounty

Currently, we do not offer a paid bug bounty program. However, we greatly appreciate responsible disclosure and will:

- Credit researchers in our CHANGELOG and documentation
- Provide recognition in our Security Hall of Fame
- Offer swag and merchandise (when available)
- Priority support for your open source projects using pytest-fastcollect

## Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE/SANS Top 25](https://cwe.mitre.org/top25/)
- [Python Security Best Practices](https://python.readthedocs.io/en/stable/library/security_warnings.html)
- [Rust Security Guidelines](https://anssi-fr.github.io/rust-guide/)

## Questions?

If you have questions about our security policy, please:
- Open a public discussion on GitHub (non-sensitive topics)
- Email the maintainers (sensitive topics)
- Check our [documentation](README.md)

---

**Last Updated**: January 2025
**Policy Version**: 1.0
