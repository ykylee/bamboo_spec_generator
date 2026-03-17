package com.example.specs.generated;

import com.atlassian.bamboo.specs.api.builders.job.Job;
import com.atlassian.bamboo.specs.api.builders.plan.Plan;
import com.atlassian.bamboo.specs.api.builders.plan.Project;
import com.atlassian.bamboo.specs.api.builders.plan.Stage;
import com.atlassian.bamboo.specs.api.builders.requirement.Requirement;
import com.atlassian.bamboo.specs.builders.task.ScriptTask;

// Sample generated Bamboo Specs source close to Bamboo Java Specs builder style.
public final class SampleAppWebPlanSpecs {
    private static final String PROJECT_KEY = "Y2026";
    private static final String PLAN_KEY = "SAMPWEB";
    private static final String YEAR = "2026";
    private static final String SCRIPT_ROOT = "scripts/generated/sample-app-web";

    private SampleAppWebPlanSpecs() {
    }

    public static Plan plan() {
        Project project = new Project()
            .key(PROJECT_KEY)
            .name("Generated Plans " + YEAR);

        return new Plan(project, "Sample App Web build plan", PLAN_KEY)
            .description("Sample App Web build plan")
            .stages(
                prepareStage(),
                buildStage(),
                staticAnalysisStage(),
                triggerFollowUpStage()
            );
    }

    public static Stage prepareStage() {
        return new Stage("Prepare")
            .jobs(new Job("Prepare Job", "PREP")
    .requirements(Requirement.equals("operating.system", "Windows"))
    .requirements(Requirement.exists("system.builder.nodejs"))
    .requirements(Requirement.exists("system.builder.nuget"))
                .tasks(new ScriptTask()
                    .fileFromPath(SCRIPT_ROOT + "/prepare_build.py")
                    .interpreterShell()));
    }

    public static Stage buildStage() {
        return new Stage("Build")
            .jobs(new Job("Build Job", "BLD")
    .requirements(Requirement.equals("operating.system", "Windows"))
    .requirements(Requirement.exists("system.builder.nodejs"))
    .requirements(Requirement.exists("system.builder.nuget"))
                .tasks(new ScriptTask()
                    .fileFromPath(SCRIPT_ROOT + "/run_build.py")
                    .interpreterShell()));
    }

    public static Stage staticAnalysisStage() {
        return new Stage("Static Analysis")
            .jobs(
                new Job("Coverity Scan", "COV")
     .requirements(Requirement.equals("operating.system", "Windows"))
     .requirements(Requirement.exists("system.builder.nodejs"))
     .requirements(Requirement.exists("system.builder.nuget"))
                    .tasks(new ScriptTask()
                        .fileFromPath(SCRIPT_ROOT + "/run_coverity.py")
                        .interpreterShell()),
                new Job("Custom Analysis", "CUST")
     .requirements(Requirement.equals("operating.system", "Windows"))
     .requirements(Requirement.exists("system.builder.nodejs"))
     .requirements(Requirement.exists("system.builder.nuget"))
                    .tasks(new ScriptTask()
                        .fileFromPath(SCRIPT_ROOT + "/run_custom_analysis.py")
                        .interpreterShell())
            );
    }

    public static Stage triggerFollowUpStage() {
        return new Stage("Trigger Follow-up")
            .jobs(new Job("Trigger Job", "TRIG")
                .tasks(new ScriptTask()
                    .fileFromPath(SCRIPT_ROOT + "/trigger_follow_up.py")
                    .interpreterShell()));
    }
}
