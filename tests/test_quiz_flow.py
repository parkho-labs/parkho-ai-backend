
import pytest
from unittest.mock import patch, MagicMock
from src.api.v1.schemas import QuestionType, DifficultyLevel, LLMProvider, InputType as ContentType, JobStatus

@pytest.mark.asyncio
async def test_quiz_flow_youtube(async_client, mock_rag_service, test_db):
    """
    Test end-to-end quiz generation from YouTube URL
    """
    client = async_client
    # 1. Mock background task processing
    with patch("src.services.content_processor.content_processor.process_content_background_sync") as mock_process:
        # Mock the RAG service in the dependency
        with patch("src.services.content_processor.get_rag_service", return_value=mock_rag_service):
            
            # 2. Create Job
            payload = {
                "input_config": [
                    {
                        "content_type": ContentType.YOUTUBE.value,
                        "id": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                    }
                ],
                "question_types": {
                    "multiple_choice": 2,
                    "true_false": 1
                },
                "difficulty_level": DifficultyLevel.INTERMEDIATE.value,
                "generate_summary": True,
                "llm_provider": LLMProvider.GEMINI.value
            }
            
            response = await client.post("/api/v1/content/process", json=payload)
            assert response.status_code == 200 or response.status_code == 207
            data = response.json()
            assert len(data) == 1
            job_id = data[0]["job_id"]
            assert job_id is not None
            
            # Verify background task was called
            mock_process.assert_called_once_with(job_id)
            
            # 3. Simulate Successful Processing (Manually update DB)
            from src.models.content_job import ContentJob
            # JobStatus imported from schemas above
            from src.models.quiz_question import QuizQuestion
            
            job = test_db.query(ContentJob).filter(ContentJob.id == job_id).first()
            job.status = JobStatus.SUCCESS
            job.title = "Test Video"
            job.update_output_config(content_text="This is a transcript of the video.")
            
            # Create mock questions
            q1 = QuizQuestion(
                job_id=job_id,
                question_id="q1",
                question="What is the answer?",
                type="multiple_choice",
                answer_config={
                    "options": {"A": "Option A", "B": "Option B", "C": "Option C", "D": "Option D"},
                    "correct_answer": "A",
                    "explanation": "Because A is correct."
                },
                max_score=10
            )
            q2 = QuizQuestion(
                job_id=job_id,
                question_id="q2",
                question="Is it true?",
                type="true_false",
                answer_config={
                    "options": ["True", "False"],
                    "correct_answer": "True",
                    "explanation": "It is true."
                },
                max_score=10
            )
            test_db.add(q1)
            test_db.add(q2)
            test_db.commit()
            
            # 4. Check Job Status
            response = await client.get(f"/api/v1/content/{job_id}/status")
            assert response.status_code == 200
            status_data = response.json()
            assert status_data["status"] == JobStatus.SUCCESS.value
            
            # 5. Get Quiz
            response = await client.get(f"/api/v1/content/{job_id}/quiz")
            assert response.status_code == 200
            quiz_data = response.json()
            assert len(quiz_data["questions"]) == 2
            
            # 6. Submit Quiz
            # In the quiz response, IDs will be the question_ids we set
            submission_payload = {
                "answers": {
                    "q1": "A",
                    "q2": "False" # Wrong answer
                }
            }
            response = await client.post(f"/api/v1/content/{job_id}/quiz", json=submission_payload)
            assert response.status_code == 200
            result_data = response.json()
            
            # Verify scoring
            # Assuming equal weight if not specified, or checks implementation details
            # If implementation simply sums correct answers:
            # Result struct: total_score, max_possible_score, percentage, results list
            assert len(result_data["results"]) == 2
            assert result_data["results"][0]["is_correct"] == True
            assert result_data["results"][1]["is_correct"] == False


@pytest.mark.asyncio
async def test_quiz_flow_with_collection(async_client, mock_rag_service, test_db):
    """
    Test flow with collection linking
    """
    client = async_client
    with patch("src.services.content_processor.content_processor.process_content_background_sync") as mock_process:
        with patch("src.services.content_processor.get_rag_service", return_value=mock_rag_service):
            
            payload = {
                "input_config": [
                    {
                        "content_type": ContentType.WEB_URL.value,
                        "id": "https://example.com"
                    }
                ],
                "question_types": {"short_answer": 1},
                "collection_name": "test_collection",
                "should_add_to_collection": True
            }
            
            response = await client.post("/api/v1/content/process", json=payload)
            assert response.status_code == 200 or response.status_code == 207
            job_id = response.json()[0]["job_id"]
            
            # Manually trigger the 'side effect' of processing - linking to collection
            # In a real integration test, we might run the actual service method, but here we
            # want to verify the orchestration logic or simply that the flag is saved.
            
            from src.models.content_job import ContentJob
            job = test_db.query(ContentJob).filter(ContentJob.id == job_id).first()
            assert job.collection_name == "test_collection"
            assert job.should_add_to_collection == True
            
            # Simulate processor checking this flag
            # We can test the processor logic separately or blindly trust the unit tests for processor.
            # Here we just verified API correctly saved the intent.


@pytest.mark.asyncio
async def test_quiz_flow_file_upload(async_client, test_db):
    """
    Test uploading a file and starting a job with it
    """
    client = async_client
    # 1. Upload File
    file_content = b"Dummy PDF content"
    files = {"file": ("test.pdf", file_content, "application/pdf")}
    response = await client.post("/api/v1/content/upload", files=files)
    assert response.status_code == 200, f"Upload failed: {response.text}"
    upload_data = response.json()
    file_id = upload_data["file_id"]
    assert file_id is not None
    
    # 2. Process File
    with patch("src.services.content_processor.content_processor.process_content_background_sync") as mock_process:
        payload = {
            "input_config": [
                {
                    "content_type": ContentType.FILES.value,
                    "id": str(file_id)
                }
            ],
            "question_types": {"multiple_choice": 1}
        }
        
        response = await client.post("/api/v1/content/process", json=payload)
        assert response.status_code == 200 or response.status_code == 207
        data = response.json()
        assert data[0]["file_id"] == str(file_id)
