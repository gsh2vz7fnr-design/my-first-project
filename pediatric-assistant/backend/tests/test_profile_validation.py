"""接口输入校验测试"""
import pytest
from pydantic import ValidationError
from app.models.user import (
    AddAllergyRequest, AddMedicalHistoryRequest,
    AddFamilyHistoryRequest, AddMedicationHistoryRequest
)


class TestAllergyValidation:
    def test_valid(self):
        """TC-PV-001"""
        req = AddAllergyRequest(allergen="鸡蛋", reaction="皮疹")
        assert req.allergen == "鸡蛋"

    def test_missing_allergen(self):
        """TC-PV-002"""
        with pytest.raises(ValidationError):
            AddAllergyRequest(reaction="皮疹")

    def test_missing_reaction(self):
        """TC-PV-003"""
        with pytest.raises(ValidationError):
            AddAllergyRequest(allergen="鸡蛋")

    def test_empty_allergen(self):
        """TC-PV-004"""
        with pytest.raises(ValidationError):
            AddAllergyRequest(allergen="", reaction="皮疹")


class TestMedicalValidation:
    def test_valid(self):
        """TC-PV-005"""
        req = AddMedicalHistoryRequest(condition="热性惊厥")
        assert req.status == "ongoing"

    def test_missing_condition(self):
        """TC-PV-006"""
        with pytest.raises(ValidationError):
            AddMedicalHistoryRequest()


class TestFamilyValidation:
    def test_valid(self):
        """TC-PV-007"""
        req = AddFamilyHistoryRequest(condition="高血压", relative="父亲")
        assert req.condition == "高血压"

    def test_missing_relative(self):
        """TC-PV-008"""
        with pytest.raises(ValidationError):
            AddFamilyHistoryRequest(condition="高血压")


class TestMedicationValidation:
    def test_valid(self):
        """TC-PV-009"""
        req = AddMedicationHistoryRequest(drug_name="布洛芬")
        assert req.drug_name == "布洛芬"

    def test_missing_drug_name(self):
        """TC-PV-010"""
        with pytest.raises(ValidationError):
            AddMedicationHistoryRequest()

    def test_empty_drug_name(self):
        """TC-PV-011"""
        with pytest.raises(ValidationError):
            AddMedicationHistoryRequest(drug_name="")
