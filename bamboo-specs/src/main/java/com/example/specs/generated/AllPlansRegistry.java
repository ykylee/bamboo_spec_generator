package com.example.specs.generated;

import java.util.List;
import com.atlassian.bamboo.specs.api.builders.plan.Plan;

// Sample generated registry for all plans in a single specs repository.
public final class AllPlansRegistry {
    private AllPlansRegistry() {
    }

    public static List<Plan> plans() {
        return List.of(
            SampleAppApiPlanSpecs.plan(),
            SampleAppWebPlanSpecs.plan()
        );
    }
}
