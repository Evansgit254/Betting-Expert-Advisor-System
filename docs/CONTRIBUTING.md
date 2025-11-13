# Contributing to Betting Expert Advisor

Thank you for considering contributing to this project!

## Code of Conduct

This project is for **educational and development purposes only**. By contributing, you agree to:

- Not facilitate illegal gambling activities
- Not enable fraud, money laundering, or exploitation
- Ensure compliance with applicable laws
- Follow ethical development practices

## Development Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/yourusername/betting-expert-advisor.git
   cd betting-expert-advisor
   ```

2. **Run setup script**
   ```bash
   bash scripts/setup.sh
   ```

3. **Activate virtual environment**
   ```bash
   source venv/bin/activate
   ```

## Making Changes

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write clean, documented code
   - Follow existing code style (use `black` for formatting)
   - Add tests for new functionality

3. **Run tests**
   ```bash
   pytest
   ```

4. **Format code**
   ```bash
   black src/ tests/
   ```

5. **Commit changes**
   ```bash
   git add .
   git commit -m "Add feature: your feature description"
   ```

6. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

7. **Open a Pull Request**

# Merge in: Development workflows from DEVELOPMENT.md

## Contribution & Development Workflow
1. Create a feature branch: `git checkout -b feature/your-feature-name`
2. Make changes (see Code Style below)
3. Run all quality gates: formatting, lint, type check, test
   ```bash
   make format
   make lint
   make type-check
   make test
   ```
   or directly with:
   ```bash
   black src/ tests/
   flake8 src/ tests/
   mypy src/
   pytest -v
   ```
4. Commit, push, and open a Pull Request

## Code Style
Follow [PEP 8], enforced by Black (100 char lines), Google-style docstrings, and type hints.
More details/examples in DEVELOPMENT.md.

## Testing
- All new features should have unit and integration tests
- Place tests in `tests/`, aim for ≥90% coverage
- Run tests (`pytest` or `make test`)

## Dev Commands
- Formatting: `make format`
- Linting: `make lint`, `flake8 src/ tests/`
- Type Checking: `make type-check`, `mypy src/`
- Testing: `make test`, `pytest`

## Debugging & Troubleshooting
- Logging: see `src/logging_config.py`, use `logger` for detailed logs
- Debug: use `import pdb; pdb.set_trace()` or IPython
- Troubleshoot errors: see 'Troubleshooting' in README/INSTALLATION.md

## Performance Profiling
- Use `src/tools/profiler.py` utilities: `@timeit`, `@profile_function`, `PerformanceMonitor` block

## New Functionality
- Register adapters, strategies, or risk modules as described in DEVELOPMENT.md

## Support
- For bugs, open a GitHub issue
- See [README.md] for architectural and system context

## Documentation

- Update README.md if adding major features
- Document all configuration options
- Add docstrings with examples
- Update .env.example for new settings

## Pull Request Guidelines

- **Clear description** of changes
- **Reference issues** being fixed (if applicable)
- **All tests passing**
- **Code formatted** with black
- **Coverage maintained** or improved
- **No breaking changes** without discussion

## Areas for Contribution

### High Priority
- Real bookmaker API implementations
- Additional data source adapters
- Model improvements (better features, algorithms)
- Backtesting enhancements
- Performance optimizations

### Medium Priority
- Web dashboard/UI
- Additional risk management strategies
- More comprehensive tests
- Documentation improvements
- Example notebooks

### Low Priority
- Code cleanup and refactoring
- Minor bug fixes
- Typo corrections

## Questions?

Open an issue for:
- Bug reports
- Feature requests
- Questions about implementation
- General discussions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

**Remember: This is an educational project. Always ensure compliance with local laws and regulations.**
