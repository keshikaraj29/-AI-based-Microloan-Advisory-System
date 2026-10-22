# SDG alignment and societal impact

## Intended contribution

The project's intended beneficiaries are small farmers, dairy operators and microenterprise borrowers; loan officers and researchers are the direct users of the analytical tools. The project makes loan terms and dataset patterns easier to inspect and supports questions about livelihood finance. These are intended benefits, not measured impacts on people.

| SDG connection | Product contribution | Concrete example | Evidence still needed |
|---|---|---|---|
| SDG 1, target 1.4: access to economic resources and financial services, including microfinance | Explain application inputs, estimated installments and the limits of recommendations | A farmer can inspect an installment estimate before a conversation with a loan officer | Comprehension study and actual access/use measures; a screen does not prove greater inclusion |
| SDG 8, target 8.3: microenterprise development and access to financial services | Compare loan-structure cohorts and narrative themes | A dairy cooperative can investigate whether cash-flow timing should affect its repayment-plan design | Seasonality and observed repayment data from that cooperative |
| SDG 8, target 8.10: expand access to banking and financial services | Lightweight local interface and explicit data/source labels | A field worker can demonstrate the interface without depending on an external chatbot API | Device/network usability study, language comprehension and accessibility testing |

The target connections above follow the United Nations' official descriptions of [SDG 1](https://sdgs.un.org/goals/goal1) and [SDG 8](https://sdgs.un.org/goals/goal8). The application does not calculate the UN's official indicator values. Account ownership, transparent missing-information states and manual payment records support a prospective pilot, but bank verification and welfare evaluation remain separate work.

## A realistic field evaluation

The delivered household-outcome importer already validates linked before/after observations and calculates descriptive changes. Use [the data guide](household_outcomes_guide.md) when real permissioned records are available. Its current template is empty, so no achieved welfare change is reported.

1. **Before the pilot:** agree with a partner institution on consent, data access, follow-up dates, a primary outcome and a comparison group/design. Identify who might be excluded by smartphone access, language, literacy or missing records.
2. **At baseline:** collect household income/consumption with units and time period, business revenue/cost, savings/assets, debt burden, prior repayment and baseline narrative. Do not infer poverty status from optimistic language.
3. **During the pilot:** record completion time, form errors, successful task completion, explanations understood, overrides by loan officers and any adverse decisions. Use anonymous usability participants where possible.
4. **At agreed follow-up:** collect the same welfare measures, business survival, installment performance and borrower feedback. Log missing follow-up and attrition by group.
5. **Analysis:** compare outcomes under the prespecified design, quantify uncertainty and confounding, disaggregate where sample sizes and permissions permit, and examine both benefit and harm.

## Candidate measures and interpretation

| Measure | Calculation/evidence | Appropriate claim |
|---|---|---|
| Task completion | Participants completing an assigned workflow / participants attempting it | Usability within the evaluated sample |
| Explanation comprehension | Correct answers on a short, independently designed questionnaire | How well that explanation worked for those participants |
| Installment punctuality | Installments paid by due date / installments due within a fixed window | Observed repayment behavior for that cohort |
| Household welfare change | Follow-up minus baseline measure, with consistent unit and observation window | Measured change; causal attribution requires the comparison design |
| Business survival | Businesses operating at follow-up / businesses observed at baseline | Survival in the observed sample; disclose attrition |
| Inclusion and possible harm | Completion, review outcomes and complaints by relevant participant groups | Differential experience that requires investigation |

## Why the present data cannot establish poverty alleviation

The accepted-loan archive is a different lending population from the intended Indian microfinance beneficiaries. Agricultural prices and dairy transactions do not provide an untreated comparison group or pre/post household welfare. A fully paid loan can coexist with hardship; an increase in revenue can coexist with rising costs. Consequently, the current system reports analytical associations, explicit-input annualization and manually recorded payments, not poverty reduction percentages.

This caution is consistent with published randomized microcredit research: Banerjee, Karlan and Zinman synthesize six evaluations and describe average effects as limited rather than transformative. Their causal design is qualitatively different from this project's exploratory data analysis. [American Economic Association, 2015](https://www.aeaweb.org/articles?id=10.1257/app.20140287)
