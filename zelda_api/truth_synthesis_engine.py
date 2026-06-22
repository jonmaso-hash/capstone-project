import logging
from .fact_assertion_models import FactAssertion, ContradictionAlert
from .truth_delta_models import ExternalDataSource
from .external_verifiers import VerifierFactory

logger = logging.getLogger(__name__)

class TruthSynthesisEngine:
    """
    Logic-based contradiction detection.
    Responsible for checking Assertions against themselves (Internal)
    and against ExternalDataSource records (External).
    """

    def run_full_analysis(self, document_source):
        """Runs the complete logic suite for all assertions in a document."""
        assertions = FactAssertion.objects.filter(document=document_source)
        logger.info(f"Synthesis Engine: Analyzing {assertions.count()} assertions for {document_source.filename}")
        
        for assertion in assertions:
            self._check_internal_consistency(assertion)
            self._query_external_sources(assertion)
        
        return True

    def _check_internal_consistency(self, assertion):
        """Finds if this assertion contradicts other insights in the SAME document."""
        same_entity_attrs = FactAssertion.objects.filter(
            document=assertion.document,
            entity_name=assertion.entity_name,
            attribute=assertion.attribute,
        ).exclude(id=assertion.id)

        for other in same_entity_attrs:
            if self._values_contradict(assertion, other):
                self._create_alert(assertion, conflicting_assertion=other)

    def _values_contradict(self, assertion1, assertion2):
        """Logic: If time periods match and numeric values differ > 10%, it's a conflict."""
        if assertion1.time_period != assertion2.time_period:
            return False
        
        if assertion1.value_numeric and assertion2.value_numeric:
            diff = abs(assertion1.value_numeric - assertion2.value_numeric)
            threshold = assertion1.value_numeric * 0.10
            return diff > threshold
        return False

    def _create_alert(self, assertion, conflicting_assertion=None, external_source=None, discrepancy=0.0):
        """Persists a ContradictionAlert to the database."""
        alert = ContradictionAlert.objects.create(
            fact_assertion=assertion,
            conflicting_assertion=conflicting_assertion,
            external_source=external_source,
            claimed_value=assertion.value,
            observed_value=str(conflicting_assertion.value) if conflicting_assertion else "External Match Found",
            discrepancy_percent=discrepancy,
            alert_level='critical' if discrepancy > 0.25 else 'medium'
        )
        logger.warning(f"Synthesis Engine: Created {alert.alert_level} alert for {assertion.attribute}")
        return alert

    def _query_external_sources(self, assertion):
        """Query ExternalDataSource models and compare."""
        sources = ExternalDataSource.objects.filter(is_active=True)
        for source in sources:
            # Dynamic lookup of the verifier class
            verifier = VerifierFactory.get_verifier(source.source_type)
            if not verifier:
                continue
                
            observed_data = verifier.fetch(assertion.entity_name, assertion.attribute)

            if observed_data:
                # Assuming _calculate_discrepancy exists in your engine or needs implementation
                discrepancy = self._calculate_discrepancy(assertion, observed_data)
                if discrepancy > 0.10: # Threshold
                    self._create_alert(assertion, external_source=source, discrepancy=discrepancy)

    def _calculate_discrepancy(self, assertion, observed_data):
        """Helper to calculate discrepancy percentage."""
        # Placeholder implementation
        return 0.0