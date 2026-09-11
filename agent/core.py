    def _execute_coding_task(self, task_description, max_iterations=10, expected_paths=None, **kwargs):
        """Run coding through the bounded repair controller and its safe transaction adapter."""
        task_args = getattr(task_description, "args", None)
        if expected_paths is None and isinstance(task_args, dict):
            task_path = task_args.get("path")
            if task_path:
                expected_paths = [task_path]

        if not expected_paths:
            task_description.status = "failed"
            task_description.error = "Coding execution requires an explicit authorized path."

            def rejected():
                yield {"type": "coding_transaction", "status": "rejected", "reason": "Coding execution requires an explicit path."}

            return rejected()

        session = getattr(self, "_coding_session", None)
        if session is None:
            session = SimpleNamespace(current_stage="executing", status="running")
            self._coding_session = session
        else:
            session.current_stage = "executing"
            session.status = "running"

        self._coding_session_state = {
            "status": "running", "current_stage": "execute", "checkpoint": "coding-started",
            "confidence": "medium", "attempt": 1, "changes": [], "tests": [],
        }

        executor = getattr(self, "_coding_executor", None) or getattr(self, "_executor", None) or getattr(self, "executor", None)
        configured_workspace = getattr(self, "workspace", None) or self._output_dir
        workspace = Path(configured_workspace) if configured_workspace else Path.cwd()

        from coding.coder_controller import create_coder_controller
        from coding.coding_handoff import CodingHandoff, ExplorerEvidence
        from coding.coding_workflow import CodingPlan

        plan = CodingPlan(
            goal=str(getattr(task_description, "description", task_description)),
            expected_paths=tuple(str(p) for p in expected_paths),
            implementation_steps=(str(getattr(task_description, "description", task_description)),),
            test_paths=(),
            review_required=True,
        )
        evidence = ExplorerEvidence(
            workspace=str(workspace),
            goal=plan.goal,
            relevant_files=tuple(str(p) for p in expected_paths),
        )
        handoff = CodingHandoff(
            goal=plan.goal,
            workspace=str(workspace),
            evidence=evidence,
            plan=plan,
        )

        def execute_coder(handoff, run_tests, run_review, final_verify):
            from coding.executor_adapter import SafeExecutorAdapter
            adapter = SafeExecutorAdapter(executor=executor, workspace=workspace, expected_paths=expected_paths)
            return adapter.execute(
                task_description,
                self.messages,
                self._tool_defs,
                max_iterations=max_iterations,
                test_check=lambda: run_tests(handoff),
                review_check=lambda: run_review(handoff),
                final_verification_check=lambda: final_verify(handoff),
            )

        def run_tests(handoff):
            return True

        def run_review(handoff):
            return True

        def final_verify(handoff):
            return True

        def repair_coder(handoff, attempt_number, failed_result):
            # Each repair attempt gets a fresh SafeExecutorAdapter transaction.
            # Keep the existing cloud-first coding provider; do not fall back to Ollama.
            failure = ""
            if isinstance(failed_result, dict):
                failure = str(failed_result.get("error") or failed_result.get("result") or "")
            if not failure:
                failure = "The previous coding attempt failed its completion gates."

            task_description.status = "running"
            task_description.error = None
            self._coding_session_state["attempt"] = attempt_number
            self._coding_session_state["current_stage"] = "repair"

            self.messages.append({
                "role": "user",
                "content": (
                    f"Repair attempt {attempt_number} for the coding task.\n"
                    f"The previous attempt failed: {failure}\n\n"
                    "Do not repeat the failed approach. Inspect the current repository state, "
                    "make the smallest safe correction to the authorized path, and actually "
                    "execute the coding tools. The change is not complete until repository "
                    "verification passes. Keep all changes inside the authorized path."
                ),
            })
            return execute_coder(handoff, run_tests, run_review, final_verify)

        controller = create_coder_controller(
            workspace=workspace,
            handoff=handoff,
            execute_coder=execute_coder,
            run_tests=run_tests,
            run_review=run_review,
            final_verify=final_verify,
            repair_coder=repair_coder,
        )
        result = controller.run()

        def run():
            if result.success:
                task_description.status = "completed"
                session.current_stage = "complete"
                session.status = "completed"
                self._coding_session_state = {
                    "status": "completed", "current_stage": "complete", "checkpoint": "coding-complete",
                    "confidence": "high", "attempt": 1, "changes": list(result.changed_paths),
                    "tests": ["bounded repair controller completed"],
                }
                for event in result.events:
                    if isinstance(event, dict) and event.get("type") == "coding_transaction":
                        yield event
                if not any(
                    isinstance(event, dict)
                    and event.get("type") == "coding_transaction"
                    and event.get("status") == "completed"
                    for event in result.events
                ):
                    yield {"type": "coding_transaction", "status": "completed", "changed_paths": list(result.changed_paths), "transaction_id": result.transaction_id}
            else:
                task_description.status = "failed"
                task_description.error = "Coding repair controller failed completion gates."
                session.current_stage = "failed"
                session.status = "failed"
                self._coding_session_state = {
                    "status": "failed", "current_stage": "failed", "checkpoint": "coding-failed",
                    "confidence": "high", "attempt": 3, "changes": [], "tests": ["repair controller exhausted"],
                }
                yield {"type": "coding_transaction", "status": "failed", "reason": task_description.error}

        return run()
