# What is lkmlstyle?

**lkmlstyle is a flexible, command-line style checker for LookML.** lkmlstyle checks LookML to see if it follows predefined or customized **rules**, showing lines in your code that don't follow the rules.

With lkmlstyle, you can:

 - Ignore rules you don't agree with
 - Modify existing rules by changing their YAML spec
 - Add new rules using simple YAML definitions

## Installation

lkmlstyle requires Python 3.10 or higher. To check your Python version, run `python --version`.

Install lkmlstyle with pip:

```
pip install lkmlstyle
```

If the installation was successful, you should be able to run this command to see a table of all style rules.

```
lkmlstyle rules
```

## Getting Started

First, clone the Git repo for your Looker project to your local environment so lkmlstyle can find `.lkml` files in your environment.

### Specifying files to check

Next, run lkmlstyle with the path to your local Looker project repo. lkmlstyle will check all files in your project that end in `.lkml` and display any rule violations.

```
lkmlstyle repos/product-analytics
```

You can pass individual or multiple files to lkmlstyle to valiate them specifically.

```
lkmlstyle repos/product-analytics/views/sessions.view.lkml
```

### Seeing the rationale for rules

If you're confused by a rule or curious why a Looker developer might want to follow it, you can add the `--show-rationale` option. lkmlstyle will display some information about why the rule exists.

```
lkmlstyle sessions.view.lkml orders.view.lkml --show-rationale
```

## Customizing the ruleset at the command line

### Showing all rules

To display all the rules and rationales defined in lkmlstyle, run this command.

```
lkmlstyle rules
```

### Ignoring rules

If you see rules you'd like to ignore, you can add the `--ignore` option and the codes for the offending rules to exclude them from testing.

`--ignore` must always be specified after all file paths, at the end of your command.

```
lkmlstyle repos/product-analytics/views/sessions.view.lkml --ignore D106 D107 M101
```

_Tip: If you find you're always ignoring certain rules, you can also adjust lkmlstyle's ruleset using a [config file](lkmlstyle.example.yaml) so you don't have to type them out every time._

### Isolating rules

Similarly, if you'd like to focus on a few rules at a time, you can provide rule codes to `--select` to _only_ test those rules.

```
lkmlstyle repos/product-analytics/views/sessions.view.lkml --select D101
```

## Overriding and adding new rules

### Modifying an existing rule

All of lkmlstyle's existing rules can be defined as YAML. In your config file, you can define custom rules modifying existing rules to fit your needs.

Let's say we wanted to modify the rule `M100`, which requires count measures be prefixed with `count_`, to require a prefix of `c_` instead.

Here's how we would do this with a custom rule override.

1. First, we'd find the YAML definition for `M100` in the [`rules.yaml` file at the root of this repo](rules.yaml).

1. Then, we would copy it to the `custom_rules` section of our `lkmlstyle.yaml` config file (see [an example here](lkmlstyle.example.yaml)) and make the following modifications:

```yaml
custom_rules:
- title: Name of count measure doesn't start with 'c_'
  code: M100
  rationale: You should explicitly state the aggregation type in the dimension name
    because it makes it easier for other developers and Explore users to understand
    how the measure is calculated.
  select:
  - measure
  filters:
  - function: block_has_valid_parameter
    parameter_name: type
    value: count
  regex: "^c_"
  negative: false
  type: PatternMatchRule
```

Since the YAML rule uses the same code `M100`, this rule definition will override the default definition of `M100`.

You can also define your own rules in YAML using the building blocks that lkmlstyle makes available. More detailed documentation on how to do this is coming soon.

_lkmlstyle is maintained by the team at [Spectacles](https://spectacles.dev)—a continuous integration tool for Looker and LookML._
